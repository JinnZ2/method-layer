# GX CASE — dominance_provenance_gap

CC0. Opened 2026-09-08. WORK ORDER N.
Deliverable is a RECORD. Stages: COMMIT -> RETRIEVE -> SCORE.

CLAIM UNDER TEST
  The retracted alpha-wolf / naturalised-dominance claim is a
  CONTRIBUTING FACTOR — one additional increment of licence layered
  onto existing entitlement. Not a cause. Strength is deliberate and
  is not escalated anywhere in this record.

---

## STAGE 1 — COMMIT (written before any retrieval)

  P1  Circulation of the claim post-retraction:
      HEAVILY DOCUMENTED
  P2  Short-chain harm, dog training / bite incidents traced to
      dominance methods:
      MEASURED, exists
  P3  Perpetration-attitude research (hostile sexism, dominance-based
      masculinity norms) correlating with violence outcomes:
      MEASURED, exists
  P4  PROVENANCE — any study tracing where perpetrators or holders
      SOURCED the belief, linking the animal literature to attitude or
      outcome research:
      PREDICTED ABSENT
  P5  Any coding of rationalisations by SOURCE in courtroom
      transcripts, interrogation records, or offender accounts:
      PREDICTED ABSENT
  P6  Workplace / institutional cost denominator:
      PREDICTED ABSENT, and absence is itself the prediction —
      periphery is uninstrumented

  Commit hash of this stage (sha256 of the P1-P6 block above, as
  committed to git before retrieval): see COMMIT_HASH below and the
  git commit that introduced this file.

## STAGE 2 — RETRIEVE (2026-09-08, after commit 99c8eb7)

RETRIEVAL INSTRUMENT, DECLARED
  Web search engine with AI-summarised result pages (US index),
  ~22 queries. Direct page reads were BLOCKED at the network egress for
  every publisher host tried (ScienceDirect, SAGE, Taylor & Francis,
  Springer, Wiley) and for every metadata API tried (Semantic Scholar,
  OpenAlex, Crossref). Abstracts were therefore read through search
  summaries, not from the papers. Consequences for the grades below:
    - presence findings (P1-P3) rest on multiple independent hits and
      are robust to this limit;
    - absence findings (P4-P6) cannot be CONFIRMED by a search
      instrument at all, and this instrument is weaker than a database
      search. Every absence below is NOT FOUND, never CONFIRMED.
  Absence status vocabulary used here:
    NOTFOUND   searched, nothing matching the measurand returned
    NODATA     not searched / not reachable
    CONFIRMED  a source states the absence (none reached that bar)

---

P1  CIRCULATION OF THE CLAIM POST-RETRACTION
  queries    Mech "alpha wolf" retraction 1999 term still widely used;
             "alpha male" wolf myth persists despite Mech correction
  found      Mech 1999 "Alpha Status, Dominance, and Division of Labor
             in Wolf Packs"; Mech's own request that the term be
             retired for natural packs and his attempt to take his 1970
             book out of print; International Wolf Center, Science
             Arena interview, Science Friday, Time archive, Wikipedia
             "Alpha Wolf" all documenting continued popular use. One
             source states academic use largely ceased in the 2000s
             while media use continued; dog-training literature shifted
             to reward-based methods after 2000.
  not found  a quantitative circulation measure (citation or media
             frequency time series). NOTFOUND.
  absence    n/a (presence prediction)
  block      measurand   documentation that the term circulates after
                         the 1999 correction
             range       English-language popular media, wolf-science
                         outreach, dog-training discourse
             instrument  web search over secondary sources
             grade       MEASURED_PRESENT
  sources    https://www.sciencearena.org/en/interviews/selfcorrection-science-absolute-truth-david-mech-wolves/
             https://wolf.org/headlines/debunking-the-alpha-wolf-why-we-need-to-rethink-our-understanding-of-wolf-packs/
             https://www.sciencefriday.com/segments/alpha-wolf-myth/
             https://time.com/archive/6934564/dog-training-and-the-myth-of-alpha-male-dominance/
             https://www.sciencenorway.no/ulv/wolf-packs-dont-actually-have-alpha-males-and-alpha-females-the-idea-is-based-on-a-misunderstanding/1850514
             https://en.wikipedia.org/wiki/Alpha_Wolf

P2  SHORT-CHAIN HARM, DOG TRAINING
  queries    Herron 2009 confrontational dominance-based training
             aggressive response; aversive dominance training dogs
             aggression bite risk systematic review
  found      Herron, Shofer & Reisner 2009, Applied Animal Behaviour
             Science 117:47-54. 140 owner surveys at a referral
             behaviour service. Confrontational methods elicited an
             aggressive response from >= 25% of dogs on which they were
             tried: hit/kick 43%, growl at dog 41%, force item release
             39%, alpha roll 31%, stare down 30%, dominance down 29%,
             grab jowls and shake 26%. Reviews (Ziv 2017; Guilherme
             Fernandes et al. 2017) associate aversive methods with
             stress indicators and aggression toward household members
             and strangers. The reviews state the causal direction is
             not established: owners of already-aggressive dogs may
             resort to these methods.
  not found  population bite-incidence records attributed to dominance
             methods. The instrumented measurand is "aggressive
             response to a technique in a referral sample", which is
             narrower than "bite incidents traced to dominance
             methods". NOTFOUND for the wider phrasing.
  absence    n/a (presence prediction)
  block      measurand   aggressive response by dogs to confrontational
                         / dominance-based techniques
             range       client-owned dogs at one US referral behaviour
                         service (Herron); owner-questionnaire samples
                         (reviews)
             instrument  owner survey; literature reviews of
                         questionnaire studies
             grade       MEASURED_PRESENT
                         (range narrower than the prediction's wording;
                         causal direction not established by the
                         instrument)
  sources    https://www.sciencedirect.com/science/article/abs/pii/S0168159108003717
             https://vmc.vet.osu.edu/sites/default/files/documents/trainingArticle.pdf
             https://www.sciencedirect.com/science/article/abs/pii/S1558787817300357
             https://www.sciencedirect.com/science/article/abs/pii/S0168159117302095

P3  PERPETRATION-ATTITUDE RESEARCH
  queries    hostile sexism intimate partner violence perpetration
             meta-analysis; masculine norms dominance conformity sexual
             violence perpetration meta-analysis
  found      A meta-analysis of 141 studies on hostile and benevolent
             sexism and violence against women (hostile sexism
             associated with tolerant attitudes and violent behaviour);
             a 62-nation comparison associating hostile sexism with IPV
             acceptance; behavioural-observation studies of couples
             (Cross et al. 2017); a 2023 meta-analysis of traditional
             masculinity and male violence against women (57 samples,
             10,772 respondents, 51 articles 1992-2021); Murnen et al.
             2002 meta-analysis (39 effect sizes, largest for hostile
             masculinity and hypermasculinity); studies linking the
             sexual-dominance norm to sexual aggression.
  not found  nothing missing relative to the prediction
  absence    n/a (presence prediction)
  block      measurand   correlation between dominance-based attitude
                         measures and violence attitudes / behaviour
             range       predominantly US samples; some cross-national
             instrument  self-report scales; meta-analysis;
                         behavioural observation
             grade       MEASURED_PRESENT
  sources    https://www.sciencedirect.com/science/article/pii/S2352250X25002684
             https://journals.sagepub.com/doi/abs/10.1177/1948550616672000
             https://www.researchgate.net/publication/367453018_Traditional_Masculinity_and_Male_Violence_Against_Women_A_Meta-Analytic_Examination
             https://link.springer.com/article/10.1023/A:1020488928736
             https://pubmed.ncbi.nlm.nih.gov/29950930/
             https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6264844/

P4  PROVENANCE — THE JOIN
  queries    (a) animal-behaviour side: as P1
             (b) violence side: as P3
             (c) join: "alpha wolf" OR "alpha male" ethology origin of
                 belief IPV perpetrators where sourced; Mech alpha wolf
                 + masculinity / gender-based violence / coercive
                 control citing both; scholarly-domain-restricted
                 query on where men acquire dominance beliefs;
                 manosphere alpha/beta terminology + violence attitudes
  found      Popular essays asserting the link (not studies).
             Scholarly manosphere literature: Ging 2019 "Alphas, Betas,
             and Incels" (Men and Masculinities 22:638-657) and
             Vallerga et al. 2022 (Analyses of Social Issues and Public
             Policy 22:602-625; 227 posts, 389,189 words) document an
             alpha / beta / incel typology of men and attribute the
             ideology to "evolution-based views of gender essentialism"
             and evolutionary-psychology framing. Exit-forum
             ethnographies (Studies in Conflict & Terrorism 2023;
             Thorburn 2023) trace entry pathways (romantic rejection,
             masculine inadequacy) and report user self-accounts of
             partner abuse after adopting the ideology.
             THESE ARE ADJACENT, NOT A JOIN. They source the vocabulary
             to an evolutionary framing at community level. None
             reached traces it to the wolf / Mech / Schenkel
             literature, and none links the animal literature to
             attitude or outcome measures within one study.
  not found  any study tracing holders' belief to the animal
             literature AND linking to attitude / outcome research.
             NOTFOUND. Whether Ging 2019 discusses the ethological
             origin in its body text could not be read (egress
             blocked): that single check is NODATA and is the first
             thing to run with a working database connection.
  absence    NOT FOUND. Not CONFIRMED.
  join hit   none found.
  block      measurand   documented provenance link, animal literature
                         -> holder belief -> attitude / outcome measure
             range       peer-reviewed literature reachable by web
                         search, 2026-09-08
             instrument  web search (see declaration); publisher and
                         metadata APIs blocked
             grade       UNMEASURED — no instrument for belief
                         provenance at population scale was found; the
                         manosphere ethnographies instrument community-
                         level sourcing only, and stop one step short
                         of the animal literature
  sources    https://journals.sagepub.com/doi/abs/10.1177/1097184X17706401
             https://spssi.onlinelibrary.wiley.com/doi/full/10.1111/asap.12308
             https://www.tandfonline.com/doi/full/10.1080/1057610X.2023.2244192
             https://journals.sagepub.com/doi/full/10.1177/13675494231153900
             https://tecscience.tec.mx/en/education-and-humanism/myth-of-the-alpha-male/
             https://brewminate.com/the-alpha-myth-unpacking-the-toxicity-of-dominance-culture-and-male-supremacy/

P5  CODING OF RATIONALISATIONS BY SOURCE
  queries    offender accounts neutralization rationalizations coded by
             source of belief; perpetrator narratives justifications
             coded "source" media culture where learned (scholarly
             domains)
  found      Neutralisation research codes accounts by TECHNIQUE TYPE
             (Sykes & Matza lineage; Maruna & Copes review; a 2025
             white-collar coding study; a 2026 Discover Psychology
             study of 28 judicial confessions from Greek appeal courts
             yielding five themes and a set of neutralisation
             techniques). One qualitative study of 21 men in IPV
             treatment (Sexuality & Culture 2019) includes "mass media"
             and "gender stereotypes" as social dimensions of the
             interviews. That is the closest item: a cultural-source
             CATEGORY appears as a theme, in treatment interviews, not
             as a per-rationalisation provenance code, and not in
             courtroom or interrogation records.
  not found  any coding scheme that tags each rationalisation with
             WHERE the holder sourced it, applied to courtroom
             transcripts, interrogation records or offender accounts.
             NOTFOUND.
  absence    NOT FOUND. Not CONFIRMED.
  block      measurand   rationalisations coded by SOURCE of belief in
                         judicial / interrogation / offender accounts
             range       peer-reviewed literature reachable by web
                         search, 2026-09-08
             instrument  web search (see declaration)
             grade       UNMEASURED — existing coding schemes measure
                         type, not provenance; no source-coding
                         instrument found
  sources    https://www.tandfonline.com/doi/full/10.1080/01639625.2018.1491696
             https://link.springer.com/article/10.1007/s44202-026-00714-7
             https://www.sciencedirect.com/science/article/pii/S294979142500079X
             https://link.springer.com/article/10.1007/s12119-019-09661-z

P6  WORKPLACE / INSTITUTIONAL COST DENOMINATOR
  queries    "alpha" dominance leadership style workplace cost
             estimate turnover economic denominator; dominance versus
             prestige leaders organizational outcomes; "Who's the
             Boss?" abstract
  found      Generic turnover-cost multipliers (roughly 90-300% of
             salary per replaced employee), not specific to dominance-
             based management. Dominance-vs-prestige research (Cheng,
             Tracy and colleagues; a 2023 conference paper) finds
             dominance-based leadership associated with lower employee
             well-being, mediated by empowerment; consultancy pieces
             associate dominant leaders with turnover. "Who's the
             Boss?" (Carter, Dudley, Lyle & Smith, JEBO 2019) measures
             leadership QUALITY and junior-officer retention in the US
             Army; it is not a dominance-style construct and computes
             no cost.
  not found  any study computing an institutional cost attributable to
             dominance-based management: no denominator. NOTFOUND.
  absence    NOT FOUND. Not CONFIRMED. Consistent with the periphery
             argument: the costs land distributed (turnover, sick
             leave, lost output across many firms) where no single
             ledger records them against the management style.
  block      measurand   institutional cost attributable to
                         dominance-based management (denominator)
             range       organisational research reachable by web
                         search, 2026-09-08
             instrument  web search (see declaration)
             grade       UNMEASURED — instruments exist for the STYLE
                         (dominance / prestige scales) and for PROXIMAL
                         outcomes (well-being, turnover intention);
                         none reached computes the denominator. Not
                         UNDERPOWERED: no denominator instrument was
                         found and shown to lack resolution.
  sources    https://www.nber.org/papers/w22383
             https://ideas.repec.org/a/eee/jeborg/v159y2019icp323-343.html
             https://www.shs-conferences.org/articles/shsconf/pdf/2023/18/shsconf_fems2023_01055.pdf
             https://www2.psych.ubc.ca/~henrich/pdfs/Cheng%20et%20al.%20(2013)%20-%20Two%20Ways%20to%20the%20Top.pdf
             https://www.strategypeopleculture.com/blog/true-cost-employee-turnover/

---

## STAGE 3 — SCORE

  P1  CORRECT      circulation post-retraction is heavily documented
  P2  CORRECT      short-chain harm measured (Herron 2009 and reviews);
                   range narrower than the prediction's wording
  P3  CORRECT      attitude-outcome correlations measured, meta-analysed
  P4  UNRESOLVED   no join hit; absence NOT FOUND, not CONFIRMED.
                   A search cannot confirm an absence. Closest adjacent
                   evidence (manosphere ethnographies) stops one step
                   short. One NODATA check outstanding (Ging 2019 body).
  P5  UNRESOLVED   no source-coding found; absence NOT FOUND, not
                   CONFIRMED
  P6  UNRESOLVED   no denominator found; absence NOT FOUND, not
                   CONFIRMED

  Scoring rule applied: a prediction of ABSENCE scores CORRECT only on
  CONFIRMED absence (a source stating that no such study exists).
  NOT FOUND leaves it UNRESOLVED. This is the NOT MEASURED / NOT FOUND
  rule from README.md applied to the scorer itself. Three UNRESOLVED
  returns are the honest output of a search instrument asked to
  establish absences.

---

## THE STRUCTURAL ARGUMENT (stated, not softened)

  Neither field is avoiding the join. It falls BETWEEN them. Animal
  behaviour retracted and moved on; violence research measures
  attitudes without asking provenance. No discipline owns the join, so
  the disciplinary structure PREDICTS the absence. This is the
  information-decoupling result applied to a specific case.

  What the retrieval adds to that argument: the nearest thing to a join
  sits in a THIRD literature (manosphere studies, in gender studies and
  terrorism studies) that neither of the two named fields cites as its
  own. That literature sources the alpha / beta vocabulary to an
  evolutionary framing and stops there. The wolf literature is one
  further step upstream and unreached. So the gap is not one missing
  study; it is a chain in which each segment is held by a field that
  does not hold the next.

## LIMITS OF THIS RECORD

  - Attribution of belief origin at population scale is genuinely
    hard. A person holding the alpha idea rarely knows they got it from
    a 1970 book about wolves, and no instrument found here asks.
  - Retrieval was by a weak instrument (search summaries; every
    database and publisher host blocked). A repeat with a bibliographic
    database is the first re-run.
  - No causal chain is claimed. The claim under test names a
    CONTRIBUTING FACTOR and nothing here escalates it.
  - The harm literatures in P2 and P3 are not aggregated and no total
    is implied.
  - This record is about a claim's circulation. It does not describe
    individuals, offenders or clinical material; the P5 entry describes
    coding schemes only.


COMMIT_HASH sha256(P1-P6 block) = de419391a7fbb284ee25eb17d9dcc3c428c1eb942643d4b9a018818ae9f8647f
HASH RULE   sha256 over the lines from the FIRST line matching /^  P1  /
            through the first following line equal to
            "      periphery is uninstrumented", inclusive, each line
            newline-terminated. The Stage 3 score table also begins
            "  P1  "; a range rule that restarts there reads past the
            block and does not reproduce the hash. Verified with the
            first-occurrence rule at commits 99c8eb7 and 62a4e01.
