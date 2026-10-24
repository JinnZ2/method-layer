#!/usr/bin/env python3
"""Execute each card's run command in a sandbox and capture the head of its output.

CC0.  Standard library only (plus ``git``, ``unshare``, ``setpriv`` from util-linux).

```text
card.run (DRAFT or confirmed)
   | allowed form ONLY:  python3 <one of the card's own integrity paths> [plain args]
   | blocked:  run is null | status PROPOSED | safety flag (re-scanned from the bytes):
   |           deletes-files / network / credentials              -> stays UNRUN, reason kept
   v
git archive <layer-3 snapshot commit> -> read-only tree      sha12 re-checked before running
   v
sandbox:  unshare -n (no network)  +  setpriv nobody (cannot write the tree)
          or, unprivileged: unshare -rn  +  tree chmod a-w
          neither available -> exit 3, nothing written
          per run: the tool's own top-level folder is a fresh writable copy,
          everything else a symlink into the read-only export; both discarded
          fresh HOME/TMPDIR per run; no proxy env; timeout 60 s, process group killed
   v
exit 0          -> run_result RUN     (status RUN)
nonzero/timeout -> run_result FAILED  (status stays UNRUN: FAILED is not RUN)
captured = first 40 lines of stdout+stderr (lines cut at 300 chars); full length + sha12 kept
```

There are no wrappers here.  A layer-3 item with no file (the M-gate, R-router
and architecture-audit possibilities) has no card and is never run.

Usage::

    python3 run_examples.py --simulators PATH --method-layer PATH [--jobs 4] [--only ID ...]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate  # noqa: E402
import rl_common as rl  # noqa: E402

TIMEOUT_S = 60
_ARG_OK = re.compile(r"^[A-Za-z0-9_./=:,+-]+$")


# ---------------------------------------------------------------------------
# sandbox
# ---------------------------------------------------------------------------

def _works(cmd: List[str]) -> bool:
    try:
        return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def detect_sandbox() -> Optional[str]:
    if not (shutil.which("unshare")):
        return None
    if os.geteuid() == 0 and shutil.which("setpriv") and \
            _works(["unshare", "-n", "setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "true"]):
        return "netns+nobody"
    if _works(["unshare", "-rn", "true"]):
        return "userns-netns+readonly-tree"
    return None


def sandbox_prefix(mode: str) -> List[str]:
    if mode == "netns+nobody":
        return ["unshare", "-n", "setpriv", "--reuid=65534", "--regid=65534", "--clear-groups"]
    return ["unshare", "-rn"]


def traversable_by_nobody(p: Path) -> bool:
    for parent in [p] + list(p.parents):
        try:
            if not (parent.stat().st_mode & 0o001):
                return False
        except OSError:
            return False
    return True


def export_tree(repo_dir: Path, commit: str, dest: Path, mode: str) -> None:
    dest.mkdir(parents=True)
    arch = subprocess.run(["git", "-C", str(repo_dir), "archive", "--format=tar", commit],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if arch.returncode != 0:
        raise SystemExit("git archive failed in %s: %s" % (repo_dir, arch.stderr.decode(errors="replace")))
    subprocess.run(["tar", "-x", "-C", str(dest), "--no-same-owner", "--no-same-permissions"],
                   input=arch.stdout, check=True)
    for root, dirs, files in os.walk(dest):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o555)
        for f in files:
            os.chmod(os.path.join(root, f), 0o444)
    os.chmod(dest, 0o555)


def run_tree(tree: Path, tool_path: str, workdir: Path, mode: str) -> Path:
    """Per-run root: the tool's own top-level folder (or, for a root-level
    tool, the root files) is a fresh writable copy; every other entry is a
    symlink into the shared read-only export.  Writes land in the copy and
    are discarded with it."""
    root = Path(tempfile.mkdtemp(prefix="rl-run-", dir=str(workdir)))
    top = tool_path.split("/", 1)[0] if "/" in tool_path else None
    for entry in sorted(tree.iterdir()):
        dest = root / entry.name
        if top is not None and entry.name == top:
            shutil.copytree(str(entry), str(dest), symlinks=True)
        elif top is None and entry.is_file():
            shutil.copy2(str(entry), str(dest))
        else:
            os.symlink(str(entry), str(dest))

    def open_up(q: str, is_dir: bool) -> None:
        if os.path.islink(q):  # never chmod through a link into the shared export
            return
        os.chmod(q, 0o777 if is_dir else 0o666)
        if mode == "netns+nobody":
            os.chown(q, 65534, 65534)

    if top is not None:
        open_up(str(root / top), True)
        for r, dirs, files in os.walk(str(root / top)):
            for d in dirs:
                open_up(os.path.join(r, d), True)
            for f in files:
                open_up(os.path.join(r, f), False)
    else:
        for f in root.iterdir():
            if f.is_file() and not f.is_symlink():
                open_up(str(f), False)
    open_up(str(root), True)
    return root


def unlock_tree(dest: Path) -> None:
    for root, dirs, _files in os.walk(dest):
        os.chmod(root, 0o755)
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o755)


# ---------------------------------------------------------------------------
# one card
# ---------------------------------------------------------------------------

def parse_command(cmd: str, paths: List[str]) -> Tuple[Optional[List[str]], str]:
    try:
        parts = shlex.split(cmd)
    except ValueError as e:
        return None, "run command does not parse: %s" % e
    if len(parts) < 2 or parts[0] not in ("python3", "python"):
        return None, "run command outside allowed form (python3 <card path> [args])"
    if parts[1] not in paths:
        return None, "run command names %s, not one of this card's paths" % parts[1]
    for a in parts[2:]:
        if not _ARG_OK.match(a) or a.startswith("/") or ".." in a.split("/"):
            return None, "run argument %r outside allowed characters" % a
    return parts[1:], ""


def capture_head(out: bytes) -> Tuple[str, int, str]:
    text = out.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    head = []
    for ln in lines[: rl.CAPTURE_LINES]:
        ln = ln.rstrip()
        if len(ln) > rl.CAPTURE_LINE_CHARS:
            ln = ln[: rl.CAPTURE_LINE_CHARS] + " [...]"
        head.append(ln)
    if len(lines) > rl.CAPTURE_LINES:
        head.append("[... %d more lines]" % (len(lines) - rl.CAPTURE_LINES))
    return "\n".join(head), len(lines), hashlib.sha256(out).hexdigest()[:12]


def run_one(card: Dict[str, Any], trees: Dict[str, Path], mode: str, workdir: Path,
            timeout: int, today: str) -> Dict[str, Any]:
    run = card.get("run")
    cmd = run.get("value") if rl.is_draft(run) else run
    locs = [l for l in card.get("integrity") or [] if isinstance(l, dict)]
    sha = locs[0]["sha12"] if locs else None
    base = {"status": "UNRUN", "captured": "", "date": "", "command": cmd, "sha12": sha}

    if card.get("status") == "PROPOSED":
        return dict(base, reason="PROPOSED: nothing to run")
    if not cmd:
        basis = run.get("basis", "") if isinstance(run, dict) else ""
        return dict(base, reason="no safe run command identified: %s" % basis)
    loc = locs[0]
    tree = trees[loc["repo"]]
    src = tree / loc["path"]
    try:
        data = src.read_bytes()
    except OSError:
        return dict(base, reason="tool file absent from snapshot tree")
    if generate.sha12(data) != loc["sha12"]:
        return dict(base, reason="snapshot bytes do not match layer 3; not run")
    flags = generate.safety_flags(data.decode("utf-8", errors="replace"))
    if flags:
        return dict(base, reason="blocked by safety scan: %s" % ", ".join(flags))
    argv, why = parse_command(cmd, [l["path"] for l in locs if l["repo"] == loc["repo"]])
    if argv is None:
        return dict(base, reason=why)

    home = Path(tempfile.mkdtemp(prefix="rl-home-", dir=str(workdir)))
    os.chmod(home, 0o777)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(home),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "MPLBACKEND": "Agg"}
    full = sandbox_prefix(mode) + [sys.executable, "-B", "-s"] + argv
    rroot = run_tree(tree, loc["path"], workdir, mode)
    try:
        proc = subprocess.Popen(full, cwd=str(rroot), env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            out, _ = proc.communicate(timeout=timeout)
            code: Optional[int] = proc.returncode
            reason = "" if code == 0 else "exit %d" % code
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            out, _ = proc.communicate()
            code = None
            reason = "timeout after %d s" % timeout
    finally:
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(rroot, ignore_errors=True)
    head, nlines, osha = capture_head(out or b"")
    status = "RUN" if code == 0 else "FAILED"
    if status == "RUN" and not head.strip():
        head = "[exit 0, no output]"
    rr = dict(base, status=status, captured=head, date=today, exit_code=code,
              output_lines=nlines, output_sha12=osha, sandbox=mode)
    if reason:
        rr["reason"] = reason
    return rr


def apply_result(card: Dict[str, Any], rr: Dict[str, Any]) -> Dict[str, Any]:
    card = dict(card)
    card["run_result"] = rr
    if card.get("status") != "PROPOSED":
        card["status"] = "RUN" if rr["status"] == "RUN" else "UNRUN"
    out = card.get("output")
    if rl.is_draft(out):
        card["output"] = rl.output_with_capture(out, rr)
    return rl.order_card(card)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--simulators", required=True, type=Path)
    ap.add_argument("--method-layer", required=True, type=Path)
    ap.add_argument("--base", type=Path, default=rl.HERE, help="reasoning-layer directory")
    ap.add_argument("--workdir", type=Path, default=Path(tempfile.gettempdir()),
                    help="where snapshot trees are exported (must be traversable by nobody when run as root)")
    ap.add_argument("--only", nargs="*", default=None, help="card ids to run")
    ap.add_argument("--rerun", action="store_true", help="re-execute cards whose capture is current")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=TIMEOUT_S)
    ap.add_argument("--date", default=date.today().isoformat())
    a = ap.parse_args(argv)

    mode = detect_sandbox()
    if mode is None:
        print("cannot run: no network-isolating sandbox (unshare -n / unshare -rn) available; nothing written")
        return 3
    if mode == "netns+nobody" and not traversable_by_nobody(a.workdir.resolve()):
        print("cannot run: --workdir %s is not traversable by nobody; pass e.g. --workdir /tmp" % a.workdir)
        return 3

    l3 = rl.load_layer3(a.base / "layer3" / rl.LAYER3_TXT.name, a.base / "layer3" / rl.LAYER3_META.name)
    cards_dir = a.base / "cards"
    cards = rl.load_cards(cards_dir)
    todo = []
    for cid, c in cards.items():
        if a.only is not None and cid not in a.only:
            continue
        rr = c.get("run_result") or {}
        run = c.get("run")
        cmd = run.get("value") if rl.is_draft(run) else run
        current = rr.get("status") in ("RUN", "FAILED") and rr.get("command") == cmd and \
            rr.get("sha12") == (c.get("integrity") or [{}])[0].get("sha12")
        if current and not a.rerun:
            continue
        todo.append(cid)

    work = Path(tempfile.mkdtemp(prefix="reasoning-layer-run-", dir=str(a.workdir)))
    os.chmod(work, 0o755)
    trees: Dict[str, Path] = {}
    try:
        for repo, clone in (("Simulators", a.simulators), ("method-layer", a.method_layer)):
            trees[repo] = work / repo
            export_tree(clone, l3.heads[repo], trees[repo], mode)
        runs = work / "homes"
        runs.mkdir()
        os.chmod(runs, 0o777)

        def job(cid: str) -> Tuple[str, Dict[str, Any]]:
            return cid, run_one(cards[cid], trees, mode, runs, a.timeout, a.date)

        counts: Dict[str, int] = {}
        with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
            for cid, rr in ex.map(job, todo):
                new = apply_result(cards[cid], rr)
                cards[cid] = new
                rl.write_card(new, cards_dir)
                counts[rr["status"]] = counts.get(rr["status"], 0) + 1
    finally:
        for t in trees.values():
            if t.exists():
                unlock_tree(t)
        shutil.rmtree(work, ignore_errors=True)

    apparatus = rl.read_yaml(a.base / "APPARATUS.yaml")
    rl.write_if_changed(a.base / "READ_FIRST.md", rl.render_read_first(apparatus, rl.load_cards(cards_dir)))
    print("run_examples.py  sandbox=%s  considered=%d  %s" % (
        mode, len(todo), "  ".join("%s=%d" % kv for kv in sorted(counts.items()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
