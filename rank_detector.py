"""Detect a rank change from a dim(k) curve instead of declaring one.

The state ``S = (rho, T, rank)`` stays notation until ``delta rank`` is
measured.  Two mechanisms produce the same observation, "more visible
structure":

* **resolution artifact** -- new samples land on the existing manifold.  The
  local intrinsic dimension is scale-invariant: more samples, same rank.
* **dimensional activation** -- new samples depart the manifold along a
  direction that carried no prior variance.  The local dimension jumps at a
  scale and then holds: more samples, same rank; finer *scale*, higher rank.

The discriminator is therefore not sample count.  It is whether the local
dimension varies with **scale** while sample density is held fixed.

Instrument::

    points (fixed record)
      |
      | centers: seeded subsample
      v
    per center: sorted distances -> prefix neighborhoods at radius k
      |
      | covariance -> eigen spectrum -> participation ratio
      v
    dim(k) = median over centers            (curve, fine -> coarse)
      |
      +-- flat              -> FLAT         resolution only, rank scored
      +-- step, fine higher, one direction  -> ACTIVATION  at k_step; emit VARIABLE_UNIDENT
      +-- step, fine higher, isotropic gain -> NOISE_FLOOR at k_step; not a named variable
      +-- step, coarse higher -> COARSE_RISE curvature / fold; scope-out, not covered
      +-- monotone drift    -> AMBIGUOUS    UNKNOWN_measurable, never scored
      +-- noisy / no plateau-> BLOCKED      sample floor

Everything here is standard library only.  Synthetic manifolds with known
rank are generated for the null construction; no external data is required.

Known limit: off-manifold noise whose amplitude sits inside the swept
window is geometrically identical to an activation at that scale when the
ambient space leaves only one normal direction.  With two or more normal
directions the two separate: an activated variable gains variance along one
direction, a noise floor gains it isotropically across the null space.  The
null suite measures and reports the residual false-positive rate before any
real use.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from bisect import bisect_right
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from branch_set import AccessKind, Branch, BranchSet, SuppressionCause
from preference_free_rank import CriterionResult

Point = Tuple[float, ...]
Matrix = List[List[float]]

SAMPLE_FLOOR = "sample_floor"
MECHANISM_ORIGIN = "more_visible_structure"

SCOPE_OUT_NOTE = (
    "zoom out = connection density to neighbouring structures; a graph "
    "measurement, not a manifold one. Flagged, not started, not covered here."
)


class Outcome(str, Enum):
    FLAT = "flat"
    ACTIVATION = "activation"
    NOISE_FLOOR = "noise_floor"
    COARSE_RISE = "coarse_rise"
    AMBIGUOUS = "ambiguous"
    BLOCKED = "blocked"


# --------------------------------------------------------------------------
# linear algebra (stdlib only)
# --------------------------------------------------------------------------


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: Sequence[float]) -> float:
    return math.sqrt(_dot(a, a))


def _matvec(m: Matrix, v: Sequence[float]) -> List[float]:
    return [_dot(row, v) for row in m]


def _quadratic(m: Matrix, v: Sequence[float]) -> float:
    return _dot(v, _matvec(m, v))


def symmetric_eigen(matrix: Matrix) -> Tuple[List[float], List[List[float]]]:
    """Cyclic Jacobi eigen-decomposition of a real symmetric matrix.

    Returns eigenvalues in descending order and the matching unit
    eigenvectors, each as a plain list.
    """

    n = len(matrix)
    a = [list(map(float, row)) for row in matrix]
    for i in range(n):
        if len(a[i]) != n:
            raise ValueError("matrix must be square")
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    d = [a[i][i] for i in range(n)]

    def rotate(m: Matrix, i: int, j: int, k: int, l: int, s: float, tau: float) -> None:
        g = m[i][j]
        h = m[k][l]
        m[i][j] = g - s * (h + g * tau)
        m[k][l] = h + s * (g - h * tau)

    for _sweep in range(100):
        off = 0.0
        for p in range(n - 1):
            for q in range(p + 1, n):
                off += abs(a[p][q])
        if off == 0.0:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                apq = a[p][q]
                if abs(apq) < 1e-300:
                    continue
                h = d[q] - d[p]
                if abs(apq) < 1e-15 * abs(h):
                    t = apq / h
                else:
                    theta = 0.5 * h / apq
                    t = 1.0 / (abs(theta) + math.sqrt(1.0 + theta * theta))
                    if theta < 0.0:
                        t = -t
                c = 1.0 / math.sqrt(1.0 + t * t)
                s = t * c
                tau = s / (1.0 + c)
                h = t * apq
                d[p] -= h
                d[q] += h
                a[p][q] = 0.0
                for j in range(p):
                    rotate(a, j, p, j, q, s, tau)
                for j in range(p + 1, q):
                    rotate(a, p, j, j, q, s, tau)
                for j in range(q + 1, n):
                    rotate(a, p, j, q, j, s, tau)
                for j in range(n):
                    rotate(v, j, p, j, q, s, tau)
        # Convergence check on the next sweep uses the updated off-diagonal.
        if off < 1e-14 * (sum(abs(x) for x in d) + 1e-300):
            break

    order = sorted(range(n), key=lambda i: -d[i])
    values = [d[i] for i in order]
    vectors = [[v[k][i] for k in range(n)] for i in order]
    return values, vectors


def participation_ratio(eigenvalues: Sequence[float]) -> float:
    """Soft dimension estimate ``(sum l)^2 / sum l^2`` over a spectrum."""

    clipped = [max(0.0, float(value)) for value in eigenvalues]
    total = sum(clipped)
    square = sum(value * value for value in clipped)
    if square <= 0.0:
        return 0.0
    return total * total / square


# --------------------------------------------------------------------------
# neighbourhood covariance sweep
# --------------------------------------------------------------------------


def _as_points(points: Iterable[Sequence[float]]) -> List[Point]:
    cloud = [tuple(float(x) for x in point) for point in points]
    if not cloud:
        raise ValueError("at least one point is required")
    dim = len(cloud[0])
    if dim == 0 or any(len(point) != dim for point in cloud):
        raise ValueError("all points must share one non-zero ambient dimension")
    for point in cloud:
        if any(not math.isfinite(x) for x in point):
            raise ValueError("points must be finite")
    return cloud


class _CenterSweep:
    """Distances from one center, sorted once, walked as growing prefixes."""

    def __init__(self, center: Point, points: Sequence[Point]) -> None:
        self.ambient = len(center)
        shifted = [tuple(x - c for x, c in zip(point, center)) for point in points]
        squared = [_dot(vec, vec) for vec in shifted]
        order = sorted(range(len(points)), key=lambda idx: squared[idx])
        self.distances = [math.sqrt(squared[idx]) for idx in order]
        self.shifted = [shifted[idx] for idx in order]

    def radius_reaching(self, count: int) -> Optional[float]:
        if count <= 0 or count > len(self.distances):
            return None
        return self.distances[count - 1]

    def covariances(
        self, radii: Sequence[float], min_neighbors: int
    ) -> List[Tuple[int, Optional[Matrix]]]:
        dim = self.ambient
        sum_x = [0.0] * dim
        sum_xx = [[0.0] * dim for _ in range(dim)]
        pos = 0
        out: List[Tuple[int, Optional[Matrix]]] = []
        for radius in radii:
            limit = bisect_right(self.distances, radius)
            while pos < limit:
                x = self.shifted[pos]
                for i in range(dim):
                    xi = x[i]
                    sum_x[i] += xi
                    row = sum_xx[i]
                    for j in range(dim):
                        row[j] += xi * x[j]
                pos += 1
            n = pos
            if n < max(min_neighbors, 2):
                out.append((n, None))
                continue
            cov = [
                [
                    (sum_xx[i][j] - sum_x[i] * sum_x[j] / n) / (n - 1)
                    for j in range(dim)
                ]
                for i in range(dim)
            ]
            out.append((n, cov))
        return out


@dataclass(frozen=True)
class ScaleSample:
    radius: float
    dim: Optional[float]
    valid_centers: int
    centers_total: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "radius": self.radius,
            "dim": self.dim,
            "valid_centers": self.valid_centers,
            "centers_total": self.centers_total,
        }


@dataclass(frozen=True)
class ActivatedDimension:
    """A previously-collapsed variable entering the record (the F/G seam)."""

    scale_of_appearance: float
    direction: Tuple[float, ...]
    prior_variance: float
    consistency: float
    null_space_isotropy: float
    centers_used: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scale_of_appearance": self.scale_of_appearance,
            "direction": list(self.direction),
            "prior_variance": self.prior_variance,
            "consistency": self.consistency,
            "null_space_isotropy": self.null_space_isotropy,
            "centers_used": self.centers_used,
        }


@dataclass
class DetectionResult:
    outcome: Outcome
    rule: str
    curve: List[ScaleSample]
    k_step: Optional[float] = None
    plateau_fine: Optional[float] = None
    plateau_coarse: Optional[float] = None
    activated: Optional[ActivatedDimension] = None
    blocker: Optional[str] = None

    @property
    def dims(self) -> List[Tuple[float, float]]:
        return [(sample.radius, sample.dim) for sample in self.curve if sample.dim is not None]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "rule": self.rule,
            "curve": [sample.to_dict() for sample in self.curve],
            "k_step": self.k_step,
            "plateau_fine": self.plateau_fine,
            "plateau_coarse": self.plateau_coarse,
            "activated": self.activated.to_dict() if self.activated else None,
            "blocker": self.blocker,
        }

    def to_criterion_result(self) -> CriterionResult:
        """Map the detection onto the ranking layer's return classes (-> G)."""

        if self.outcome is Outcome.ACTIVATION:
            payload: Dict[str, Any] = {
                "scale_of_appearance": self.k_step,
                "activated_dimension": self.activated.to_dict() if self.activated else None,
                "rule": self.rule,
            }
            return CriterionResult.variable_unidentified(note=json.dumps(payload, sort_keys=True))
        if self.outcome is Outcome.FLAT:
            assert self.plateau_fine is not None
            return CriterionResult.scored(self.plateau_fine, note=self.rule)
        if self.outcome is Outcome.NOISE_FLOOR:
            return CriterionResult.unknown_measurable(note=self.rule)
        if self.outcome is Outcome.COARSE_RISE:
            return CriterionResult.unknown_measurable(note=f"{self.rule}; {SCOPE_OUT_NOTE}")
        if self.outcome is Outcome.AMBIGUOUS:
            return CriterionResult.unknown_measurable(note=self.rule)
        return CriterionResult.blocked(self.blocker or SAMPLE_FLOOR, note=self.rule)


def _spread(values: Sequence[float]) -> float:
    return max(values) - min(values)


def _linear_fit_residual(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0.0:
        return sum((y - mean_y) ** 2 for y in ys)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sxx
    intercept = mean_y - slope * mean_x
    return sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))


@dataclass(frozen=True)
class _StepFit:
    fine_end: int
    coarse_start: int
    fine_mean: float
    coarse_mean: float
    residual: float


class RankDetector:
    """Sweep scale at fixed sample density and read the dim(k) curve.

    All tolerances are declared up front; nothing is learned from the data
    being read.  ``radii`` may be supplied explicitly; otherwise the window
    runs from the radius at which the median center reaches ``min_neighbors``
    to half the median data diameter.
    """

    def __init__(
        self,
        *,
        radii: Optional[Sequence[float]] = None,
        n_scales: int = 12,
        n_centers: int = 32,
        min_neighbors: Optional[int] = None,
        min_valid_fraction: float = 0.5,
        min_scales: int = 4,
        flat_tol: float = 0.35,
        step_min: float = 0.5,
        plateau_tol: float = 0.3,
        step_vs_drift: float = 0.5,
        isotropy_max: float = 0.5,
        seed: int = 0,
    ) -> None:
        if radii is not None:
            radii = [float(r) for r in radii]
            if not radii or any(r <= 0 for r in radii) or any(
                b <= a for a, b in zip(radii, radii[1:])
            ):
                raise ValueError("radii must be positive and strictly ascending")
        if n_scales < 2:
            raise ValueError("n_scales must be at least 2")
        if n_centers < 1:
            raise ValueError("n_centers must be at least 1")
        if min_neighbors is not None and min_neighbors < 2:
            raise ValueError("min_neighbors must be at least 2")
        if not 0.0 < min_valid_fraction <= 1.0:
            raise ValueError("min_valid_fraction must lie in (0, 1]")
        if min_scales < 4:
            raise ValueError("min_scales must be at least 4 (two plateaus of two)")
        for name, value in (
            ("flat_tol", flat_tol),
            ("step_min", step_min),
            ("plateau_tol", plateau_tol),
            ("step_vs_drift", step_vs_drift),
            ("isotropy_max", isotropy_max),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        self.radii = radii
        self.n_scales = n_scales
        self.n_centers = n_centers
        self.min_neighbors = min_neighbors
        self.min_valid_fraction = min_valid_fraction
        self.min_scales = min_scales
        self.flat_tol = flat_tol
        self.step_min = step_min
        self.plateau_tol = plateau_tol
        self.step_vs_drift = step_vs_drift
        self.isotropy_max = isotropy_max
        self.seed = seed

    # -- sampling ---------------------------------------------------------

    def _floor(self, ambient: int) -> int:
        return self.min_neighbors if self.min_neighbors is not None else max(16, 6 * ambient)

    def _centers(self, cloud: Sequence[Point]) -> List[int]:
        rng = random.Random(self.seed)
        count = min(self.n_centers, len(cloud))
        return sorted(rng.sample(range(len(cloud)), count))

    def _sweeps(self, cloud: Sequence[Point]) -> List[_CenterSweep]:
        return [_CenterSweep(cloud[idx], cloud) for idx in self._centers(cloud)]

    def _window(self, sweeps: Sequence[_CenterSweep], floor: int) -> Optional[List[float]]:
        if self.radii is not None:
            return list(self.radii)
        floors = [s.radius_reaching(floor) for s in sweeps]
        if any(value is None for value in floors):
            return None
        r_min = statistics.median(floors)  # type: ignore[arg-type]
        r_max = 0.5 * statistics.median(s.distances[-1] for s in sweeps)
        if r_min <= 0.0 or r_max <= r_min * 1.5:
            return None
        ratio = (r_max / r_min) ** (1.0 / (self.n_scales - 1))
        return [r_min * ratio ** i for i in range(self.n_scales)]

    def sweep(
        self, points: Iterable[Sequence[float]]
    ) -> Tuple[List[ScaleSample], List[List[Tuple[int, Optional[Matrix]]]]]:
        """Return the dim(k) curve and the per-center covariances behind it."""

        cloud = _as_points(points)
        ambient = len(cloud[0])
        floor = self._floor(ambient)
        sweeps = self._sweeps(cloud)
        radii = self._window(sweeps, floor)
        if radii is None:
            return [], []
        per_center = [s.covariances(radii, floor) for s in sweeps]
        curve: List[ScaleSample] = []
        for scale_idx, radius in enumerate(radii):
            estimates: List[float] = []
            for covs in per_center:
                _, cov = covs[scale_idx]
                if cov is None:
                    continue
                values, _ = symmetric_eigen(cov)
                estimates.append(participation_ratio(values))
            valid = len(estimates)
            enough = valid >= max(1, math.ceil(self.min_valid_fraction * len(sweeps)))
            dim = statistics.median(estimates) if enough else None
            curve.append(ScaleSample(radius, dim, valid, len(sweeps)))
        return curve, per_center

    # -- reading ----------------------------------------------------------

    def _best_step(self, radii: Sequence[float], dims: Sequence[float]) -> Optional[_StepFit]:
        n = len(dims)
        logs = [math.log(r) for r in radii]
        best: Optional[_StepFit] = None
        for fine_end in range(1, n - 2):
            fine = dims[: fine_end + 1]
            if _spread(fine) > self.plateau_tol:
                continue
            fine_mean = sum(fine) / len(fine)
            for coarse_start in range(fine_end + 1, n - 1):
                coarse = dims[coarse_start:]
                if _spread(coarse) > self.plateau_tol:
                    continue
                coarse_mean = sum(coarse) / len(coarse)
                jump = fine_mean - coarse_mean
                if abs(jump) < self.step_min:
                    continue
                residual = 0.0
                for idx in range(n):
                    if idx <= fine_end:
                        predicted = fine_mean
                    elif idx >= coarse_start:
                        predicted = coarse_mean
                    else:
                        frac = (logs[idx] - logs[fine_end]) / (logs[coarse_start] - logs[fine_end])
                        predicted = fine_mean + frac * (coarse_mean - fine_mean)
                    residual += (dims[idx] - predicted) ** 2
                candidate = _StepFit(fine_end, coarse_start, fine_mean, coarse_mean, residual)
                if best is None or (candidate.residual, coarse_start - fine_end) < (
                    best.residual,
                    best.coarse_start - best.fine_end,
                ):
                    best = candidate
        return best

    def _activated_direction(
        self,
        per_center: Sequence[Sequence[Tuple[int, Optional[Matrix]]]],
        fine_idx: int,
        coarse_idx: int,
        coarse_dim: float,
        k_step: float,
    ) -> Optional[ActivatedDimension]:
        directions: List[List[float]] = []
        priors: List[float] = []
        isotropies: List[float] = []
        for covs in per_center:
            _, fine_cov = covs[fine_idx]
            _, coarse_cov = covs[coarse_idx]
            if fine_cov is None or coarse_cov is None:
                continue
            ambient = len(coarse_cov)
            values, vectors = symmetric_eigen(coarse_cov)
            if values[0] <= 0.0:
                continue
            kept = int(round(coarse_dim))
            kept = min(max(kept, 1), ambient - 1)
            null_basis = vectors[kept:]
            # Fine covariance restricted to the coarse null space.
            projected = [
                [_quadratic(fine_cov, u) if i == j else _dot(u, _matvec(fine_cov, w))
                 for j, w in enumerate(null_basis)]
                for i, u in enumerate(null_basis)
            ]
            sub_values, sub_vectors = symmetric_eigen(projected)
            top = sub_vectors[0]
            if sub_values[0] <= 0.0:
                continue
            isotropies.append(
                max(0.0, sub_values[1]) / sub_values[0] if len(sub_values) > 1 else 0.0
            )
            direction = [0.0] * ambient
            for weight, basis in zip(top, null_basis):
                for i in range(ambient):
                    direction[i] += weight * basis[i]
            length = _norm(direction)
            if length == 0.0:
                continue
            direction = [x / length for x in direction]
            if directions and _dot(direction, directions[0]) < 0.0:
                direction = [-x for x in direction]
            directions.append(direction)
            priors.append(_quadratic(coarse_cov, direction) / values[0])
        if not directions:
            return None
        ambient = len(directions[0])
        mean = [sum(vec[i] for vec in directions) / len(directions) for i in range(ambient)]
        length = _norm(mean)
        if length == 0.0:
            return None
        mean = [x / length for x in mean]
        consistency = sum(abs(_dot(mean, vec)) for vec in directions) / len(directions)
        return ActivatedDimension(
            scale_of_appearance=k_step,
            direction=tuple(mean),
            prior_variance=statistics.median(priors),
            consistency=consistency,
            null_space_isotropy=statistics.median(isotropies),
            centers_used=len(directions),
        )

    def read(
        self,
        curve: Sequence[ScaleSample],
        per_center: Optional[Sequence[Sequence[Tuple[int, Optional[Matrix]]]]] = None,
    ) -> DetectionResult:
        """Classify a dim(k) curve.  Declared tolerances only; no fitting to taste."""

        curve = list(curve)
        valid = [(idx, s.radius, s.dim) for idx, s in enumerate(curve) if s.dim is not None]
        if len(valid) < self.min_scales:
            return DetectionResult(
                Outcome.BLOCKED,
                rule=(
                    f"{len(valid)} valid scale(s) < min_scales={self.min_scales} "
                    f"-> blocked({SAMPLE_FLOOR})"
                ),
                curve=curve,
                blocker=SAMPLE_FLOOR,
            )
        indices = [idx for idx, _, _ in valid]
        radii = [r for _, r, _ in valid]
        dims = [d for _, _, d in valid]
        span = _spread(dims)
        if span < self.flat_tol:
            level = statistics.median(dims)
            return DetectionResult(
                Outcome.FLAT,
                rule=f"span={span:.3f} < flat_tol={self.flat_tol} -> flat (resolution only)",
                curve=curve,
                plateau_fine=level,
                plateau_coarse=level,
            )
        step = self._best_step(radii, dims)
        drift_residual = _linear_fit_residual([math.log(r) for r in radii], dims)
        if step is not None and step.residual <= self.step_vs_drift * drift_residual:
            k_step = math.sqrt(radii[step.fine_end] * radii[step.coarse_start])
            if step.fine_mean > step.coarse_mean:
                activated = None
                if per_center is not None:
                    activated = self._activated_direction(
                        per_center,
                        indices[step.fine_end],
                        indices[step.coarse_start],
                        step.coarse_mean,
                        k_step,
                    )
                if per_center is not None and activated is None:
                    return DetectionResult(
                        Outcome.BLOCKED,
                        rule="step found but no center valid at both plateaus "
                        f"-> blocked({SAMPLE_FLOOR})",
                        curve=curve,
                        k_step=k_step,
                        plateau_fine=step.fine_mean,
                        plateau_coarse=step.coarse_mean,
                        blocker=SAMPLE_FLOOR,
                    )
                if activated is not None and activated.null_space_isotropy > self.isotropy_max:
                    return DetectionResult(
                        Outcome.NOISE_FLOOR,
                        rule=(
                            f"step {step.fine_mean:.2f} -> {step.coarse_mean:.2f} at k_step="
                            f"{k_step:.4g}, fine side higher, but null-space gain is isotropic "
                            f"({activated.null_space_isotropy:.2f} > {self.isotropy_max}) "
                            "-> noise_floor (no single direction; not a named variable)"
                        ),
                        curve=curve,
                        k_step=k_step,
                        plateau_fine=step.fine_mean,
                        plateau_coarse=step.coarse_mean,
                        activated=activated,
                    )
                direction_note = (
                    f", one direction (isotropy {activated.null_space_isotropy:.2f})"
                    if activated is not None
                    else ", direction unavailable (curve only)"
                )
                return DetectionResult(
                    Outcome.ACTIVATION,
                    rule=(
                        f"step {step.fine_mean:.2f} -> {step.coarse_mean:.2f} at k_step="
                        f"{k_step:.4g}, fine side higher{direction_note} -> activation"
                    ),
                    curve=curve,
                    k_step=k_step,
                    plateau_fine=step.fine_mean,
                    plateau_coarse=step.coarse_mean,
                    activated=activated,
                )
            return DetectionResult(
                Outcome.COARSE_RISE,
                rule=(
                    f"step {step.fine_mean:.2f} -> {step.coarse_mean:.2f} at k_step="
                    f"{k_step:.4g}, coarse side higher -> coarse_rise (not activation)"
                ),
                curve=curve,
                k_step=k_step,
                plateau_fine=step.fine_mean,
                plateau_coarse=step.coarse_mean,
            )
        diffs = [b - a for a, b in zip(dims, dims[1:]) if b != a]
        if diffs:
            same_sign = max(sum(1 for x in diffs if x > 0), sum(1 for x in diffs if x < 0))
            if same_sign / len(diffs) >= 0.75:
                return DetectionResult(
                    Outcome.AMBIGUOUS,
                    rule=(
                        f"span={span:.3f} with monotone drift and no plateau pair "
                        "-> ambiguous (UNKNOWN_measurable, do not score)"
                    ),
                    curve=curve,
                )
        return DetectionResult(
            Outcome.BLOCKED,
            rule=f"span={span:.3f}, noisy, no plateau -> blocked({SAMPLE_FLOOR})",
            curve=curve,
            blocker=SAMPLE_FLOOR,
        )

    def detect(self, points: Iterable[Sequence[float]]) -> DetectionResult:
        curve, per_center = self.sweep(points)
        if not curve:
            return DetectionResult(
                Outcome.BLOCKED,
                rule=f"scale window unavailable at this density -> blocked({SAMPLE_FLOOR})",
                curve=[],
                blocker=SAMPLE_FLOOR,
            )
        return self.read(curve, per_center)


def local_dimension(
    points: Iterable[Sequence[float]],
    center: Sequence[float],
    radius: float,
    *,
    min_neighbors: int = 2,
) -> Tuple[int, Optional[float]]:
    """Participation-ratio dimension of one neighbourhood, or None below the floor."""

    cloud = _as_points(points)
    sweep = _CenterSweep(tuple(float(x) for x in center), cloud)
    (count, cov), = sweep.covariances([float(radius)], min_neighbors)
    if cov is None:
        return count, None
    values, _ = symmetric_eigen(cov)
    return count, participation_ratio(values)


# --------------------------------------------------------------------------
# density sweep: the complementary axis (sample count at fixed scale)
# --------------------------------------------------------------------------


@dataclass
class DensitySweep:
    radius: float
    samples: List[Tuple[float, Optional[float]]]
    rises: Optional[bool]
    rule: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "radius": self.radius,
            "samples": [list(item) for item in self.samples],
            "rises": self.rises,
            "rule": self.rule,
        }


def density_sweep(
    points: Iterable[Sequence[float]],
    radius: float,
    *,
    fractions: Sequence[float] = (0.25, 0.5, 1.0),
    n_centers: int = 32,
    min_neighbors: Optional[int] = None,
    step_min: float = 0.5,
    seed: int = 0,
) -> DensitySweep:
    """Vary sample count at one fixed scale.  Rank rising here = undersampled."""

    cloud = _as_points(points)
    ambient = len(cloud[0])
    floor = min_neighbors if min_neighbors is not None else max(16, 6 * ambient)
    rng = random.Random(seed)
    order = list(range(len(cloud)))
    rng.shuffle(order)
    detector = RankDetector(radii=[radius], n_centers=n_centers, min_neighbors=floor, seed=seed)
    samples: List[Tuple[float, Optional[float]]] = []
    for fraction in fractions:
        if not 0.0 < fraction <= 1.0:
            raise ValueError("fractions must lie in (0, 1]")
        keep = max(1, int(round(fraction * len(cloud))))
        subset = [cloud[idx] for idx in order[:keep]]
        curve, _ = detector.sweep(subset)
        samples.append((fraction, curve[0].dim if curve else None))
    valid = [dim for _, dim in samples if dim is not None]
    if len(valid) < 2:
        return DensitySweep(radius, samples, None, f"fewer than two valid fractions -> blocked({SAMPLE_FLOOR})")
    rises = valid[-1] - valid[0] >= step_min
    rule = (
        f"dim {valid[0]:.2f} -> {valid[-1]:.2f} across sample fractions; "
        + ("rises -> undersampled" if rises else "invariant -> not undersampled")
    )
    return DensitySweep(radius, samples, rises, rule)


# --------------------------------------------------------------------------
# synthetic manifolds with KNOWN rank
# --------------------------------------------------------------------------


def _orthonormal_frame(ambient: int, rng: random.Random) -> List[List[float]]:
    frame: List[List[float]] = []
    while len(frame) < ambient:
        vec = [rng.gauss(0.0, 1.0) for _ in range(ambient)]
        for basis in frame:
            coeff = _dot(vec, basis)
            vec = [x - coeff * b for x, b in zip(vec, basis)]
        length = _norm(vec)
        if length < 1e-8:
            continue
        frame.append([x / length for x in vec])
    return frame


def _embed(coords: Sequence[Sequence[float]], frame: Sequence[Sequence[float]]) -> List[Point]:
    ambient = len(frame[0])
    out: List[Point] = []
    for coord in coords:
        vec = [0.0] * ambient
        for weight, basis in zip(coord, frame):
            for i in range(ambient):
                vec[i] += weight * basis[i]
        out.append(tuple(vec))
    return out


def _tangent_coords(
    n: int, d: int, rng: random.Random, density_exponent: float
) -> List[List[float]]:
    coords: List[List[float]] = []
    for _ in range(n):
        u = [rng.random() for _ in range(d)]
        if density_exponent:
            # First coordinate drawn from density proportional to exp(beta * u).
            x = rng.random()
            u[0] = math.log1p(x * math.expm1(density_exponent)) / density_exponent
        coords.append(u)
    return coords


def _check_manifold_args(n: int, d: int, ambient: int, extra: int = 1) -> None:
    if n < 1:
        raise ValueError("n must be positive")
    if d < 1 or d + extra > ambient:
        raise ValueError("need 1 <= d and d + extra normal directions <= ambient")


def flat_manifold(
    n: int,
    d: int,
    ambient: int,
    *,
    seed: int = 0,
    density_exponent: float = 0.0,
) -> List[Point]:
    """Rank-``d`` unit patch embedded in ``ambient`` dims by a random frame."""

    _check_manifold_args(n, d, ambient, extra=0)
    rng = random.Random(seed)
    frame = _orthonormal_frame(ambient, rng)
    return _embed(_tangent_coords(n, d, rng, density_exponent), frame[:d])


def anisotropic_noise_manifold(
    n: int,
    d: int,
    ambient: int,
    *,
    tangent_sigma: float = 0.05,
    normal_sigma: float = 0.0,
    seed: int = 0,
) -> List[Point]:
    """Rank ``d`` plus Gaussian noise; unequal sigma per tangent axis, isotropic off-manifold."""

    _check_manifold_args(n, d, ambient)
    rng = random.Random(seed)
    frame = _orthonormal_frame(ambient, rng)
    coords = []
    for u in _tangent_coords(n, d, rng, 0.0):
        row = [u[i] + rng.gauss(0.0, tangent_sigma * (i + 1) / d) for i in range(d)]
        row += [rng.gauss(0.0, normal_sigma) for _ in range(ambient - d)]
        coords.append(row)
    return _embed(coords, frame)


def curved_manifold(
    n: int,
    d: int,
    ambient: int,
    *,
    curvature: float = 1.0,
    seed: int = 0,
) -> List[Point]:
    """Rank ``d`` paraboloid patch: normal offset = curvature * |u - 1/2|^2."""

    _check_manifold_args(n, d, ambient)
    rng = random.Random(seed)
    frame = _orthonormal_frame(ambient, rng)
    coords = []
    for u in _tangent_coords(n, d, rng, 0.0):
        bend = curvature * sum((x - 0.5) ** 2 for x in u)
        coords.append(list(u) + [bend])
    return _embed(coords, frame[: d + 1])


def thick_manifold(
    n: int,
    d: int,
    ambient: int,
    *,
    thickness: float = 0.1,
    seed: int = 0,
) -> List[Point]:
    """Rank ``d`` patch with one normal direction uniformly filled to ``thickness``.

    This is the activation model: the normal direction has no variance at
    scales far above ``thickness`` and full variance below it.  The frame's
    ``d``-th vector is the true activated direction.
    """

    _check_manifold_args(n, d, ambient)
    if thickness <= 0:
        raise ValueError("thickness must be positive")
    rng = random.Random(seed)
    frame = _orthonormal_frame(ambient, rng)
    coords = []
    for u in _tangent_coords(n, d, rng, 0.0):
        coords.append(list(u) + [rng.uniform(-thickness / 2.0, thickness / 2.0)])
    return _embed(coords, frame[: d + 1])


def manifold_frame(ambient: int, seed: int = 0) -> List[List[float]]:
    """The random frame used by the generators above for a given seed."""

    return _orthonormal_frame(ambient, random.Random(seed))


# --------------------------------------------------------------------------
# null construction: known rank, no activation, must read FLAT
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class NullCase:
    family: str
    params: Dict[str, float]
    true_rank: int
    outcome: Outcome
    rule: str
    dims: Tuple[Optional[float], ...]

    @property
    def false_positive(self) -> bool:
        return self.outcome is Outcome.ACTIVATION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family": self.family,
            "params": dict(self.params),
            "true_rank": self.true_rank,
            "outcome": self.outcome.value,
            "rule": self.rule,
            "dims": list(self.dims),
            "false_positive": self.false_positive,
        }


@dataclass
class NullReport:
    cases: List[NullCase]
    positive_control: Optional[DetectionResult]

    @property
    def false_positive_rate(self) -> float:
        if not self.cases:
            return 0.0
        return sum(1 for case in self.cases if case.false_positive) / len(self.cases)

    @property
    def per_family(self) -> Dict[str, float]:
        families: Dict[str, List[NullCase]] = {}
        for case in self.cases:
            families.setdefault(case.family, []).append(case)
        return {
            name: sum(1 for c in cases if c.false_positive) / len(cases)
            for name, cases in sorted(families.items())
        }

    @property
    def positive_control_detected(self) -> Optional[bool]:
        if self.positive_control is None:
            return None
        return self.positive_control.outcome is Outcome.ACTIVATION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "false_positive_rate": self.false_positive_rate,
            "per_family": self.per_family,
            "positive_control_detected": self.positive_control_detected,
            "positive_control": self.positive_control.to_dict() if self.positive_control else None,
            "cases": [case.to_dict() for case in self.cases],
        }

    def format(self) -> str:
        lines = ["NULL CONSTRUCTION (known rank, no activation)", "-" * 46]
        for case in self.cases:
            params = ", ".join(f"{k}={v:g}" for k, v in case.params.items())
            dims = " ".join("--" if d is None else f"{d:.2f}" for d in case.dims)
            flag = "FALSE POSITIVE" if case.false_positive else "ok"
            lines.append(f"{case.family:<20} rank={case.true_rank} {params}")
            lines.append(f"  dim(k): {dims}")
            lines.append(f"  {case.outcome.value:<12} {flag}")
        lines.append("-" * 46)
        for family, rate in self.per_family.items():
            lines.append(f"{family:<20} false-positive rate {rate:.2f}")
        lines.append(f"{'overall':<20} false-positive rate {self.false_positive_rate:.2f}")
        if self.positive_control is not None:
            dims = " ".join(
                "--" if s.dim is None else f"{s.dim:.2f}" for s in self.positive_control.curve
            )
            lines.append(f"{'positive_control':<20} {self.positive_control.outcome.value}")
            lines.append(f"  dim(k): {dims}")
            lines.append(f"  {self.positive_control.rule}")
        return "\n".join(lines)


def null_suite(
    *,
    n_points: int = 3000,
    d: int = 1,
    ambient: int = 3,
    seed: int = 0,
    detector: Optional[RankDetector] = None,
    positive_thickness: Optional[float] = 0.1,
) -> NullReport:
    """Swing every known confound with the true rank held fixed.

    Families: anisotropic noise, curvature, nonuniform density.  Each can fake
    a step.  A positive control (``thick_manifold``) is run alongside so a
    zero false-positive rate is not mistaken for a detector that never fires.
    """

    detector = detector or RankDetector(seed=seed)
    cases: List[NullCase] = []

    def run(family: str, params: Dict[str, float], points: Sequence[Point]) -> None:
        result = detector.detect(points)
        cases.append(
            NullCase(
                family=family,
                params=params,
                true_rank=d,
                outcome=result.outcome,
                rule=result.rule,
                dims=tuple(sample.dim for sample in result.curve),
            )
        )

    for i, (tangent, normal) in enumerate(((0.02, 0.0), (0.05, 0.0), (0.05, 0.003))):
        run(
            "anisotropic_noise",
            {"tangent_sigma": tangent, "normal_sigma": normal},
            anisotropic_noise_manifold(
                n_points, d, ambient, tangent_sigma=tangent, normal_sigma=normal, seed=seed + i
            ),
        )
    for i, curvature in enumerate((0.5, 2.0)):
        run(
            "curvature",
            {"curvature": curvature},
            curved_manifold(n_points, d, ambient, curvature=curvature, seed=seed + 10 + i),
        )
    for i, beta in enumerate((2.0, 4.0)):
        run(
            "nonuniform_density",
            {"density_exponent": beta},
            flat_manifold(n_points, d, ambient, seed=seed + 20 + i, density_exponent=beta),
        )
    positive = None
    if positive_thickness is not None:
        positive = detector.detect(
            thick_manifold(n_points, d, ambient, thickness=positive_thickness, seed=seed + 30)
        )
    return NullReport(cases, positive)


# --------------------------------------------------------------------------
# order test: does zoom-in commute with zoom-out?
# --------------------------------------------------------------------------


def crop(points: Iterable[Sequence[float]], center: Sequence[float], radius: float) -> List[Point]:
    """Zoom in: keep the record inside a ball.  Loses structure above ``radius``."""

    cloud = _as_points(points)
    c = tuple(float(x) for x in center)
    return [p for p in cloud if _norm([x - y for x, y in zip(p, c)]) <= radius]


def coarse_grain(points: Iterable[Sequence[float]], radius: float, *, seed: int = 0) -> List[Point]:
    """Zoom out: greedy cover at ``radius``; clusters replaced by centroids.

    Loses structure below ``radius``.  Deterministic for a given seed.
    """

    cloud = _as_points(points)
    if radius <= 0:
        raise ValueError("radius must be positive")
    rng = random.Random(seed)
    order = list(range(len(cloud)))
    rng.shuffle(order)
    seeds: List[Point] = []
    sums: List[List[float]] = []
    counts: List[int] = []
    r2 = radius * radius
    for idx in order:
        p = cloud[idx]
        for k, s in enumerate(seeds):
            if sum((a - b) ** 2 for a, b in zip(p, s)) <= r2:
                for i, x in enumerate(p):
                    sums[k][i] += x
                counts[k] += 1
                break
        else:
            seeds.append(p)
            sums.append(list(p))
            counts.append(1)
    return [tuple(x / n for x in total) for total, n in zip(sums, counts)]


def _record_discrepancy(a: Sequence[Point], b: Sequence[Point]) -> Optional[float]:
    if not a or not b:
        return None

    def mean_nn(src: Sequence[Point], dst: Sequence[Point]) -> float:
        total = 0.0
        for p in src:
            total += math.sqrt(min(sum((x - y) ** 2 for x, y in zip(p, q)) for q in dst))
        return total / len(src)

    return 0.5 * (mean_nn(a, b) + mean_nn(b, a))


@dataclass
class OrderTestResult:
    center: Tuple[float, ...]
    k_in: float
    k_out: float
    read_radius: float
    path_in_then_out: Tuple[int, Optional[float]]
    path_out_then_in: Tuple[int, Optional[float]]
    commutator: Optional[float]
    record_discrepancy: Optional[float]
    rule: str
    tolerance: float = 0.1

    @property
    def commutes(self) -> Optional[bool]:
        """True when the recovered structure agrees within ``tolerance``; None if lost."""

        if self.commutator is None:
            return None
        return self.commutator < self.tolerance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commutes": self.commutes,
            "tolerance": self.tolerance,
            "center": list(self.center),
            "k_in": self.k_in,
            "k_out": self.k_out,
            "read_radius": self.read_radius,
            "path_in_then_out": list(self.path_in_then_out),
            "path_out_then_in": list(self.path_out_then_in),
            "commutator": self.commutator,
            "record_discrepancy": self.record_discrepancy,
            "rule": self.rule,
        }


def order_test(
    points: Iterable[Sequence[float]],
    k_in: float,
    k_out: float,
    *,
    center: Optional[Sequence[float]] = None,
    read_radius: Optional[float] = None,
    min_neighbors: Optional[int] = None,
    tolerance: float = 0.1,
    seed: int = 0,
) -> OrderTestResult:
    """Compare zoom-in-then-out against zoom-out-then-in on one record.

    Zoom in = ``crop`` at ``k_in``.  Zoom out = ``coarse_grain`` at ``k_out``.
    Recovered structure = the local dimension read at ``read_radius`` around
    ``center`` on each path's output.  ``commutator`` is the absolute
    difference of the two readings; 0 is a real result and ``commutes`` says
    whether it lands inside the declared ``tolerance``.  ``record_discrepancy``
    is the symmetric mean nearest-neighbour distance between the two output
    records, in units of ``k_out``.
    """

    cloud = _as_points(points)
    ambient = len(cloud[0])
    if k_in <= 0 or k_out <= 0:
        raise ValueError("k_in and k_out must be positive")
    if center is None:
        centroid = [sum(p[i] for p in cloud) / len(cloud) for i in range(ambient)]
        center = min(cloud, key=lambda p: sum((x - y) ** 2 for x, y in zip(p, centroid)))
    c = tuple(float(x) for x in center)
    read_radius = float(read_radius) if read_radius is not None else 0.5 * k_in
    floor = min_neighbors if min_neighbors is not None else max(16, 6 * ambient)

    record_1 = coarse_grain(crop(cloud, c, k_in), k_out, seed=seed)
    record_2 = crop(coarse_grain(cloud, k_out, seed=seed), c, k_in)

    def reading(record: Sequence[Point]) -> Tuple[int, Optional[float]]:
        if not record:
            return 0, None
        return local_dimension(record, c, read_radius, min_neighbors=floor)

    read_1 = reading(record_1)
    read_2 = reading(record_2)
    if read_1[1] is None or read_2[1] is None:
        commutator = None
        rule = f"a path lost the reading (below floor {floor}) -> commutator undefined; blocked({SAMPLE_FLOOR})"
    else:
        commutator = abs(read_1[1] - read_2[1])
        verdict = "commutes" if commutator < tolerance else "does not commute"
        rule = (
            f"|dim(in,out) - dim(out,in)| = |{read_1[1]:.3f} - {read_2[1]:.3f}| = "
            f"{commutator:.3f} (tolerance {tolerance:g}) -> {verdict}"
        )
    discrepancy = _record_discrepancy(record_1, record_2)
    if discrepancy is not None:
        discrepancy /= k_out
    return OrderTestResult(
        center=c,
        k_in=float(k_in),
        k_out=float(k_out),
        read_radius=read_radius,
        path_in_then_out=read_1,
        path_out_then_in=read_2,
        commutator=commutator,
        record_discrepancy=discrepancy,
        rule=rule,
        tolerance=float(tolerance),
    )


# --------------------------------------------------------------------------
# output -> F: one branch set for "more visible structure"
# --------------------------------------------------------------------------

MECHANISM_UNDERSAMPLED = "undersampled"
MECHANISM_SCALE_SUPPRESSED = "scale_suppressed"
MECHANISM_COLLAPSED = "dimensionally_collapsed"
MECHANISM_DISCRIMINATOR = "dim(k) curve at fixed sample density; density sweep at fixed scale"


def mechanism_branch_set(*, cost: float = 1.0) -> BranchSet:
    """The three generators behind "more visible structure", filed as one set."""

    return BranchSet(
        [
            Branch(
                id=MECHANISM_UNDERSAMPLED,
                generator="sample floor: structure exists at this scale but too few points resolve it",
                origin_pattern=MECHANISM_ORIGIN,
                predicted_divergence="dim rises with sample count at fixed scale; dim(k) flat at fixed density",
                discriminator=MECHANISM_DISCRIMINATOR,
                cost=cost,
                suppression_cause=SuppressionCause.PRIOR,
            ),
            Branch(
                id=MECHANISM_SCALE_SUPPRESSED,
                generator="variance exists in a direction but only below the observation scale",
                origin_pattern=MECHANISM_ORIGIN,
                predicted_divergence="dim(k) steps up toward fine scale and plateaus; invariant to sample count",
                discriminator=MECHANISM_DISCRIMINATOR,
                cost=cost,
                suppression_cause=SuppressionCause.ACCESS,
                access_kind=AccessKind.INSTRUMENT_MISSING,
            ),
            Branch(
                id=MECHANISM_COLLAPSED,
                generator="variable pinned by a constraint; zero variance at every scale in this record",
                origin_pattern=MECHANISM_ORIGIN,
                predicted_divergence="dim(k) flat and sample-count invariant; the dimension appears only in a new record",
                discriminator=MECHANISM_DISCRIMINATOR,
                cost=cost,
                suppression_cause=SuppressionCause.PRIOR,
            ),
        ]
    )


def eliminate_from_outcome(
    branch_set: BranchSet,
    detection: DetectionResult,
    density: Optional[DensitySweep] = None,
) -> BranchSet:
    """Apply one detector reading (and optional density sweep) to the branch set.

    Eliminations are recorded, never deleted.  Ambiguous, blocked and
    coarse-rise readings eliminate nothing.
    """

    def window() -> str:
        radii = [s.radius for s in detection.curve if s.dim is not None]
        return f"[{min(radii):.4g}, {max(radii):.4g}]" if radii else "[]"

    undersampled = branch_set.get(MECHANISM_UNDERSAMPLED)
    suppressed = branch_set.get(MECHANISM_SCALE_SUPPRESSED)
    collapsed = branch_set.get(MECHANISM_COLLAPSED)

    if density is not None and density.rises is not None:
        if density.rises:
            if detection.outcome is Outcome.FLAT:
                collapsed.eliminate(f"density sweep: {density.rule}")
        else:
            undersampled.eliminate(f"density sweep: {density.rule}")

    if detection.outcome is Outcome.ACTIVATION:
        collapsed.eliminate(f"rank detector: {detection.rule}")
    elif detection.outcome is Outcome.FLAT:
        suppressed.eliminate(f"rank detector: dim(k) flat over window {window()}; {detection.rule}")

    open_branches = branch_set.test_queue()
    if len(open_branches) == 1:
        open_branches[0].mark_survived()
    return branch_set


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _load_points(path: str) -> List[Point]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict) and "points" in data:
        data = data["points"]
    if not isinstance(data, list):
        raise ValueError("expected a JSON list of points or {'points': [...]}")
    return _as_points(data)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    detect_cmd = sub.add_parser("detect", help="read the dim(k) curve of a JSON point cloud")
    detect_cmd.add_argument("path")
    detect_cmd.add_argument("--json", action="store_true", help="emit the full result as JSON")

    null_cmd = sub.add_parser("null", help="run the null construction and print the report")
    null_cmd.add_argument("--n-points", type=int, default=3000)
    null_cmd.add_argument("--rank", type=int, default=1)
    null_cmd.add_argument("--ambient", type=int, default=3)
    null_cmd.add_argument("--seed", type=int, default=0)
    null_cmd.add_argument("--positive-thickness", type=float, default=0.1)
    null_cmd.add_argument("--json", action="store_true")

    order_cmd = sub.add_parser("order", help="zoom-in/zoom-out commutator on a JSON point cloud")
    order_cmd.add_argument("path")
    order_cmd.add_argument("k_in", type=float)
    order_cmd.add_argument("k_out", type=float)
    order_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "detect":
        result = RankDetector().detect(_load_points(args.path))
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        else:
            dims = " ".join("--" if s.dim is None else f"{s.dim:.2f}" for s in result.curve)
            print(f"dim(k): {dims}")
            print(f"{result.outcome.value}: {result.rule}")
        return 0
    if args.command == "null":
        report = null_suite(
            n_points=args.n_points,
            d=args.rank,
            ambient=args.ambient,
            seed=args.seed,
            positive_thickness=args.positive_thickness,
        )
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True) if args.json else report.format())
        return 0
    result = order_test(_load_points(args.path), args.k_in, args.k_out)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True) if args.json else result.rule)
    return 0


__all__ = [
    "MECHANISM_COLLAPSED",
    "MECHANISM_DISCRIMINATOR",
    "MECHANISM_ORIGIN",
    "MECHANISM_SCALE_SUPPRESSED",
    "MECHANISM_UNDERSAMPLED",
    "SAMPLE_FLOOR",
    "SCOPE_OUT_NOTE",
    "ActivatedDimension",
    "DensitySweep",
    "DetectionResult",
    "NullCase",
    "NullReport",
    "OrderTestResult",
    "Outcome",
    "RankDetector",
    "ScaleSample",
    "anisotropic_noise_manifold",
    "coarse_grain",
    "crop",
    "curved_manifold",
    "density_sweep",
    "eliminate_from_outcome",
    "flat_manifold",
    "local_dimension",
    "manifold_frame",
    "mechanism_branch_set",
    "null_suite",
    "order_test",
    "participation_ratio",
    "symmetric_eigen",
    "thick_manifold",
]


if __name__ == "__main__":
    sys.exit(main())
