# Spike 2 — can something cheap throw out most trials, so the expensive model only reads a few?

**Status: CURRENT. This is the work.** Read `README.md` and `CONTEXT.md` first.

Written 2026-09-29. Self-contained: everything it relies on is explained here before it is
used, in plain words. It replaces earlier drafts whose plan was wrong; ignore those.

No website, no app, no container, no agent framework. Code written here can be thrown away.

---

## Words used throughout

Set out once so nothing later has to be guessed at.

- **Trial** — a study testing a treatment. Each one publishes a long block of text listing
  who may and may not join.
- **Rule** — one item in that list. A trial has about 43 of them on average.
- **Trait** — something true about a patient: their age, whether they had a particular drug
  before, whether the cancer has spread to the brain.
- **Definite rule** — one that settles the matter on its own. *"People who have had drug X
  before cannot join."*
- **Conditional rule** — one that doesn't. *"People who have had drug X before cannot join,
  unless it was more than six months ago."* Whether it applies depends on extra detail.
- **Throw out** — decide a trial is impossible for this patient and remove it from
  consideration.
- **Wrongly thrown out** — a trial the patient actually could have joined, removed by
  mistake. This is the error that matters most, because nothing later puts it back.
- **Shortlist** — the trials still standing after the cheap step has thrown out what it can.
- **The big model** — an expensive, very capable language model, used by sending text to a
  company's service and paying per word.
- **A small trained model** — a model a few hundred times smaller, which we train ourselves
  and run on our own rented hardware, where the cost per item is close to nothing.
- **The answer key** — a file already on disk in which the big model read all 1,308 trials
  and recorded, for two traits, what each trial's rules say about them.

---

## Who does what

- **Will** — decides scope, checks things that only need careful reading, and has to be able
  to explain every choice to an interviewer.
- **Grok, in Cursor** — writes and runs all the code. Push back if something here looks wrong.
- **Claude** — designs, reviews at the checkpoints, explains. Does not run pipelines and does
  not spend API credit.

**Nothing in this plan asks Will to make a medical judgment.** Where a check would need
medical knowledge, either it is automated or the limitation is written down and left. Every
hand-check below is careful reading of English, nothing more.

**Money rules.** Count tokens and dollars from the first call. Ask Will before any single run
that would cost more than about $25. Three steps sit near that line. Assume about 43 rules per
trial when estimating — an earlier run cost 2.2 times its estimate by assuming trials were
simpler than they are.

---

# Part 1 — What we already know

The whole plan rests on these. None of it needs redoing.

### The data on disk

`data/nsclc_recruiting.jsonl` holds **1,308 trials** — every trial that was recruiting
patients for the commonest kind of lung cancer as of 28 September 2026. One free query
produced it, from a government registry of 604,566 studies, of which about 124,000 involve
cancer of some kind.

Each trial record has a few tidy, machine-readable fields — is it recruiting, what disease,
what ages, which sex, where are its sites — and then one long block of ordinary prose listing
the rules. That prose is usually split into two lists: a *can-join* list, where every item
must describe you, and a *cannot-join* list, where any item describing you rules you out.

**The same trait can sit on either list, and it means the opposite thing in each place.**
"Previous immunotherapy" on the can-join list means the trial wants people who had it. On the
cannot-join list it means those people are refused. This is the difficulty the whole project
turns on.

Measured across the 1,308 trials: the rules block averages **3,581 characters** and runs to
**20,203** at the longest. A script that splits the two lists by finding the heading works on
**1,234** trials, needs a looser rule for **46**, and finds no heading at all in **28**.

### The answer key

The big model has already read all 1,308 trials for **two traits** — whether the patient has
had immunotherapy before, and whether the cancer has spread to the brain. For each trial and
each trait it recorded one of eight verdicts, with a word-for-word quote from the trial as
support:

| Verdict | Meaning |
|---|---|
| `required` | the trial wants people who have this |
| `allowed` | accepts them, doesn't demand it, sets no limit |
| `allowed_with_exception` | accepts them, but with a stated limit |
| `barred` | refuses them, no exception |
| `barred_with_exception` | refuses them except in stated cases |
| `both_classifications` | one passage wants it, another refuses it |
| `not_mentioned` | the trial says nothing about it |
| `unclear` | mentions it without saying which way |

**No human has checked this key** beyond four hand-corrections. Step 9 addresses that as far
as it can be addressed.

### What the first spike found

The first spike tried the obvious cheap approach: turn text into numbers so that similar
meanings get similar numbers, then find the trials whose numbers sit closest to a question.
**It does not work for this problem.** Asked "which trials refuse people who already had
immunotherapy," it scored every trial in a narrow band between 0.40 and 0.65 on a zero-to-one
scale. The spread among trials that genuinely refuse was about 0.10. The gap between trials
that *require* the trait and trials that *refuse* it was about **0.01** — a hundredth. And
**115 of the 168** trials that specifically *want* patients who had immunotherapy scored above
the typical refusing trial.

When the variation inside one group is ten times the distance between two groups, sorting by
that number mixes them together. Plain word-matching beat this approach on both traits.

**But the big model reading the text works.** All 1,308 trials, both traits, eight minutes
running six at a time, **1,735,341 words in and 194,803 out, $7.26.**

### What Step 1 of this spike found

The big model read 300 of the 1,308 trials and listed every trait each trial's rules depend on.

- **13,033 traits, 43 per trial.**
- **5,578 differently-worded traits**, of which **77% appear exactly once.**
- The 40 commonest cover only **24%** of all the rules.
- **Not one** of the 300 trials has all its traits inside those 40.

**What that rules out:** you cannot read every trial once, fill in a fixed set of columns, and
then answer patients by filtering a spreadsheet. There is no fixed set of columns big enough.
Whatever we build has to cope with traits nobody listed in advance.

**Two useful leftovers.** A record of how this text actually words each trait — eight
different wordings for one genetic marker, four for one infection, and one common
abbreviation appearing zero times. And 13,033 pairs of (trait name, the exact sentence it came
from).

### What it costs to read everything

From the first spike's own word counts: 1,735,341 in and 194,803 out across 1,308 trials is
roughly **1,327 words in and 149 out per trial**. Assessing a real patient needs a bit more —
the patient's description goes in, and a verdict with quotes comes out — so call it **1,500 in
and 200 out per trial.**

At the big model's published prices of $2.50 per million words in and $15.00 per million out:

- 1,500 × $2.50 ÷ 1,000,000 = $0.00375
- 200 × $15.00 ÷ 1,000,000 = $0.00300
- **about $0.0068 per trial**, so **about $9 to check one patient against all 1,308 trials.**

A cheaper model at $0.75 and $4.50 per million does the same for about **$2.65 per patient**.

A person doing this by hand spends 30 to 90 minutes per patient. **So $9 is already cheap
enough to sell.** That matters more than it sounds, and Part 2 explains why.

---

# Part 2 — What this spike is actually testing

### Question one: how good is simply reading everything?

Send every trial's full rules text to the big model along with the patient, and let it decide.
No cleverness. Part 1 says this costs about $9 per patient at the current size. **Nobody has
measured how accurate it is.** That is the thing to beat, and it might turn out to be the
answer.

### Question two: can something cheap throw out most trials first?

If a cheap step can remove most trials before the big model reads anything, the same system
works at a size where reading everything is impossible. If it cannot, this project is "a
structured filter plus the big model reading everything," and the write-up says so.

### Why question two matters — the arithmetic

Reading everything is fine at 1,308 trials and hopeless at 124,000. Take all the cancer
trials. A tidy-field filter runs first — this patient's cancer type, still recruiting, sites
near enough, age in range — leaving perhaps 1,500. Then, at the measured $0.0068 per trial:

| If the cheap step throws out | Trials left to read | Cost per patient |
|---|---:|---:|
| nothing | 1,500 | $10.13 |
| half | 750 | $5.06 |
| **70%** | **450** | **$3.04** |
| 90% | 150 | $1.01 |

**70% is the target.** That makes the full cancer registry affordable, and it is a modest
target because the tidy-field filter already did the coarse work.

### But throwing out more is not the goal

**Throwing out a trial the patient could have joined is permanent.** Nothing later puts it
back. Throwing out too few trials only costs money.

And because a patient has several traits, and a trial must survive the cheap step on every
one, mistakes multiply:

| If it wrongly throws out this share, per trait | Share of joinable trials still standing after six traits |
|---|---:|
| 2% | 89% |
| 5% | 74% |
| 10% | 53% |

A step that removes 90% of trials while wrongly discarding 10% of the good ones is worse than
one that removes 60% while wrongly discarding 1%.

**So the headline result is two numbers together** — how much gets thrown out, against how
often the wrong thing gets thrown out — drawn as a curve so an operating point can be picked
from it. Never a single score.

### Why the cheap step has to be a model we train, not a cheap rented one

The obvious shortcut is to skip training and have a cheap rented model judge each rule. The
arithmetic says that saves nothing.

Reading whole trials is about 1,500 words per trial, so 1,308 trials is about 1.96 million
words. Now cost the rule-by-rule version: six traits, each with roughly 750 trials that have
some rule about it and one or two relevant lines apiece, is around 9,000 rules. Each needs its
own request — instructions, the trait, the patient's situation, the rule — about 250 words. So
about **2.25 million words**, which is *more* than reading every trial in full, because the
instructions get paid for 9,000 times instead of 1,308.

**A rented model at the rule level is a more expensive filter, not a cheaper one.** The only
way rule-by-rule beats reading everything is a model whose cost per item is effectively zero —
one we train and run ourselves. That is the entire reason for Step 6.

---

# Part 3 — The design being tested

Four stages. The rule that governs everything: **each stage must cost less per trial than the
one after it.** A stage that costs as much as the next one is not saving work, just moving it.

## Stage 1 — filter on the tidy fields

An ordinary database query on the machine-readable fields: disease, still recruiting, age
range, sex, trial site locations. No prose, no searching, no model.

**Already proven and not in question.** The 1,308-trial file *is* this stage's output for one
patient profile. 604,566 records down to 1,308, one query, no cost.

One wrinkle, worth noting and not solving here: the disease field is free text, so a trial may
name the same cancer three different ways.

## Stage 2 — the cheap step

**This is what the spike exists to test.**

### Prepared once, in advance, before any patient

1. **Every trial's rules split into separate lines**, each labelled with its trial and which
   of the two lists it came from.
2. **A set of numbers computed for every line**, so lines can be looked up by rough meaning.
   Individual lines, not whole trials — the first spike showed that one line's meaning gets
   drowned when 43 of them are squeezed into one set of numbers.
3. **A word index over the lines**, so looking up a phrase returns the lines containing it
   without reading everything.

### When a patient arrives

**First, one request to the big model takes the patient description apart** into a list of
traits. Each trait gets three things:

| What | Example | Why it is kept separate |
|---|---|---|
| A name, with no direction and no number in it | `previous platinum chemotherapy` | The name is what gets searched for, and searching only ever looks for a subject |
| The patient's situation | has it / doesn't have it / a value | Direction is not a search term |
| Which of three kinds it is | plain yes-or-no / one-of-many / number | Each kind gets compared differently. Number traits are dropped here — see Part 4 |

**The three kinds, because they are compared differently.**

- **Plain yes-or-no** — the patient either has it or doesn't, and nothing else is implied.
  Previous chemotherapy. An autoimmune condition. Cancer spread to the brain.
- **One-of-many** — the patient has exactly one item from a set of alternatives, which means
  they don't have any of the others. Which genetic marker their tumour carries. Which stage the
  disease is at. **These are recorded as a field with a value** — `genetic marker = C`,
  `stage = 4` — not as a long list of things the patient doesn't have. The comparison does the
  work: a trial requiring marker A fails this patient because C is not A.
- **Number** — dropped at this stage, see Part 4.

The one-of-many kind matters more than it sounds, because **a trial requiring one particular
genetic marker is probably the single most trial-eliminating rule in this whole set** — most
trials in this disease are built around one marker. Missing that kind would mean missing the
strongest filter available.

The only thing the system has to be told is that these alternatives exclude each other. It is
obvious to a person reading "the patient's tumour carries marker C" that they therefore don't
carry marker A, and invisible to the system unless the instructions say so. **The trial side
needs nothing extra** — recording which marker a trial asks for is the whole content of that
rule anyway.

One request per patient. A couple of cents. This is not a per-trial cost.

**Second, find the lines that might have a rule about each trait** — word-index matches, plus
the lines whose numbers sit nearest the trait name. Take everything either method finds. This
step is trying not to miss anything and does not care about picking up extras, because an
extra just gets judged and dropped.

**Third, a small trained model judges each candidate line.** It reads the line, the trait, and
the patient's situation **all together as one piece of text**, and returns one of three
answers:

- **throw out** — this rule means the patient cannot join.
- **keep** — it doesn't.
- **can't tell** — not decidable from this line alone.

**Fourth, decide the trial.** It is thrown out only if some line came back *throw out* with
high enough confidence. *Can't tell* keeps it. **And a trial with no candidate line for a
trait keeps it too** — a trial that never mentions kidney function has no kidney rule, so the
patient clears it. **Silence is a pass.** Keeping only trials that *mention* the patient's
traits would throw away the most accommodating trials in the whole set, which are exactly the
ones most likely to accept this patient.

### Why this kind of model, and why it is allowed here

Two kinds of model get confused, and the difference is the reason this design might work.

The **first kind** turns each piece of text into numbers *separately*, then compares the two
sets of numbers. The trial's numbers are therefore worked out without ever seeing the patient,
so they would have to capture every rule and every direction in advance, and then a comparison
of two fixed sets of numbers would have to sort out which applies to this patient. It cannot.
That is precisely what the first spike measured — a gap of 0.01 between "requires" and
"refuses."

The **second kind** reads both pieces of text *together* as a single input and outputs an
answer directly. Direction can be handled because the trait is in front of the model while it
reads the rule. This is the same shape as a long-standing task in which a model reads two
sentences and says whether one contradicts the other — something models a few hundred million
parameters in size have done well for years. Contradiction and negation are exactly what that
task is about.

The second kind cannot be prepared in advance, because it needs both pieces of text at once,
so it has to run when the patient arrives. That is affordable because a small model judging
short text costs almost nothing per item when run in batches, whereas a rented model per trial
costs what reading costs — which would defeat the purpose.

## Stage 3 — the big model reads what survived

The big model reads each surviving trial's **whole** rules text — not just the matched lines —
one request per trial, several at a time. It returns a verdict, the rules a human still has to
check, and word-for-word quotes.

The whole text and not the matched lines, for three reasons. Rules refer to each other
("cohort B only"), so a line read alone can be misleading. **This system must never tell
anyone they qualify** — it returns candidates plus the rules a human must verify — and that
means it has to be able to point out rules the patient description never raised. And quoting
requires having the text.

This stage also settles every number trait, which stage 2 skipped.

## Stage 4 — put them in order

One short request that ranks the surviving trials using the verdicts from stage 3.

---

# Part 4 — Number traits are left out on purpose

**Decided 28 September 2026.** A trait whose decision needs the patient's number compared
against the trial's number is left out of the cheap step entirely, and settled by the big model
in stage 3.

**Why.** Real numeric rules cannot be handled by pattern-matching. One says a blood test must
be "no more than 1.5 times the upper limit of normal" — the limit varies from laboratory to
laboratory, so there is no fixed number to compare against at all. Another gives two
alternative requirements in different units for different quantities, joined by "or", with the
comparison flipping direction between them. Pattern-matching would produce confident wrong
answers rather than honest failures.

**This costs nothing in accuracy.** A trait we don't filter on simply means those trials stay
in the shortlist, and stage 3 settles them. Leaving number traits out makes the shortlist
bigger. It cannot lose a trial the patient could have joined.

**The rule is: leave out the trait, not every line containing a digit.** Plenty of category
rules mention numbers incidentally — "brain metastases treated and stable for at least four
weeks", "surgery within six months". The trait there is a category and the number is beside the
point. Stripping every line with a digit would throw away a large share of ordinary rules and
leave a test that is easier than reality, which is the dangerous direction.

| Trait | In or out | Why |
|---|---|---|
| previous platinum chemotherapy | **in** | plain yes-or-no |
| cancer spread to the brain | **in** | plain yes-or-no, even when the text says "stable for four weeks" |
| autoimmune disease | **in** | plain yes-or-no |
| which genetic marker the tumour carries | **in** | one-of-many. Compared by "is the patient's value the one this trial asks for", not by size |
| disease stage | **in** | one-of-many. A short fixed list of labels |
| performance-status score | **out** | a number. The cheapest one to reconsider later if the cheap step isn't throwing out enough |
| number of previous treatment courses | **out** | a number |
| every blood and organ test | **out** | numbers, in inconsistent units, often relative to a laboratory's own range |

**Write this down before results exist:** every "share thrown out" figure this spike produces
counts only the category traits. A real shortlist would be larger than one that also handled
numbers.

---

# Part 5 — What we test against

**The trials** are the 1,308 described in Part 1, with the answer key described there.

**The patients** are **20 invented ones**, already written, in `data/fake_patients.md` and
`data/fake_patients_draw.json`. No real patient data is used at any point. Their traits were
generated by a random draw with the seed recorded, because both Will and Claude have seen the
answer key's contents and picking traits by hand would tilt the set toward things the system
handles. Six constraints on that draw are documented in the file, three of them corrections
where independently rolled traits produced people who could not exist.

**The set is balanced on purpose, not realistic on purpose.** Five patients in each of the four
combinations of the two traits the answer key covers, and of the ten whose cancer has spread to
the brain, five treated-and-stable and five untreated. Those two cases trip different kinds of
rule. So no "average across patients" figure from this set is an estimate of what would happen
in a real clinic — and the balancing pushes results in the pessimistic direction, since the
brain trait has the worst ratio of conditional to definite rules in the whole answer key.

**Correct answers come out of the answer key for free.** If an invented patient has had
immunotherapy before, the key already says which trials should be thrown out on that trait
(`barred`), which must certainly be kept (`required`, `allowed`), and which genuinely cannot be
settled (`barred_with_exception`, `unclear`). No human has to check 1,308 records per patient.

## Three rules for splitting the data, and the third is the one that decides everything

**Three splits, not two: train, tune, and test.** The confidence setting and the stopping point
get chosen on the *tune* split. **The test split is used once, at the end, after everything is
fixed.** Choosing a setting by looking at test results would make every headline number
worthless, and Step 6's method makes that an easy trap to fall into.

**Split by trial, not by line.** Trials copy boilerplate from each other heavily, so the same
sentence turning up in both training and test would flatter every score.

**Hold back one trait entirely.** Train on five traits, test on a sixth the model has never
seen. This is the measurement that decides whether the design works at all, because Part 1
established that this text uses 5,578 differently-worded traits with 77% appearing once — so
the design has to handle traits nobody listed in advance. **If the model only works on the
traits it trained on, it is the fixed-spreadsheet design that Step 1 already ruled out.**
Performance on trained traits would be reassuring and would mean almost nothing.

---

# Part 6 — Approaches deliberately not tried

- **Training the first kind of model on whole patients and whole trials.** Ruled out for the
  reason in Part 3: joining a trial means satisfying several requirements at once, including
  ones about numbers, and comparing two fixed sets of numbers cannot express "this patient's
  value is below this trial's limit." Two patients differing in one score have nearly identical
  numbers and opposite answers.
- **Pattern-matching numeric limits.** Part 4.
- **A published benchmark called TREC Clinical Trials** as the thing we measure against. It is
  an annual competition run by a US standards agency; its 2021 and 2022 rounds published
  invented patient case notes with human judgments of which trials suited them. Those judgments
  say "this trial suits this patient" and never "this trial has a rule about kidney function,
  pointing this way." Without per-trait labels they cannot measure the cheap step at all, and
  their patients have diseases this set of trials does not cover. Keep for a possible later
  sanity check of the whole pipeline. **Never as training material** — it is the only
  independent human-made ground truth available anywhere in this project, and training on it
  would leave nothing to test against.
- **Preparing number-sets for the whole registry.** Every rule in all 604,566 trials would be
  roughly 14 million sets of numbers, about 86 gigabytes — far past any free hosted database.

# Part 7 — Things that must not change without a decision logged

Changing any of these needs Will's agreement and an entry in `DECISIONS.md`.

1. **The system never tells anyone they qualify.** It returns candidate trials plus the rules a
   human must check.
2. **No real patient data, ever.**
3. **The cheap step sends nothing per trial to a rented model.** One request per patient to take
   the description apart is fine; a small model we trained is fine. The whole cost argument in
   Part 2 depends on this.
4. **Silence keeps the trial, and so does "can't tell."** A trial is thrown out only on
   positive, confident evidence.
5. **Invented patients' traits stay as drawn**, with the seed recorded.
6. **Split by trial, and hold back one whole trait.**
7. **Anything Will hand-checks is careful reading of English only.** Nothing in this plan asks
   him for a medical judgment.
8. **Report a range, not a bare percentage,** on any sample under about 200 items.
9. **Every deciding number goes in `THRESHOLDS.md` before the step that uses it runs**, and is
   never edited afterwards. Some of the numbers below are reasoned from arithmetic and say so;
   others are frank guesses and say so. Git history is the proof none moved to suit a result.

---

# Part 8 — The steps, in order

Ordered so the cheapest ways of killing the idea come first. **Steps 2 and 3 cost nothing and
either of them can end the project**, so they run before anything is built or bought.

Numbering starts at 2 because Step 1 is already done and its number is baked into filenames on
disk.

### Step 1 — ALREADY DONE, DO NOT RE-RUN

Ran 28 September 2026. Asked whether a fixed set of columns could cover what patients ask
about. It cannot — 13,033 traits at 43 per trial, 5,578 different wordings, the 40 commonest
covering 24% of rules, not one of 300 trials fully covered. Full numbers in Part 1, reasoning
and two disclosures in `DECISIONS.md`. Cost $6.72. Files: `scripts/step1_concepts.py`,
`scripts/step1_analyze.py`, `data/step1_*`.

### Step 2 — What is the best the cheap step could possibly do? (half a day, free)

**The cheapest thing that could kill the whole idea, so it runs first.**

Many rules are conditional — *"cannot join if the cancer has spread to the brain, unless it was
treated and has been stable for four weeks."* The cheap step is only allowed to throw a trial
out when it is certain, and a conditional rule cannot make it certain unless the patient
description happens to contain the extra detail. So conditional rules always keep the trial.

**That puts a ceiling on how much can ever be thrown out, and the ceiling has nothing to do with
how good any model is.** It is a fact about how the rules are written.

The answer key already shows how severe this is:

| | definite refusals (`barred`) | conditional refusals (`barred_with_exception`) | `required` |
|---|---:|---:|---:|
| previous immunotherapy | 259 | 87 | 168 |
| spread to the brain | **124** | **417** | 47 |

For the brain trait there are 417 trials — nearly a third of all of them — that refuse
conditionally and therefore can never be thrown out. A flawless model gets 124 out of 1,308
from that trait, about 9%.

**Method.** Assume a *perfect* cheap step and build nothing. For each invented patient and each
trait, walk the answer key and mark every trial:

For a plain yes-or-no trait:

- `barred` and the patient has it → **throw out**
- `required` and the patient does not have it → **throw out**
- `barred_with_exception` → **can't tell, keep**
- everything else → **keep**

For a one-of-many trait, where the trial's answer is a list of values:

- the trial names a required list, and the patient's value is **not** in it → **throw out**
- the trial names a refused list, and the patient's value **is** in it → **throw out**
- the trial names no list for that trait → **keep**
- the list carries a condition attached to it → **can't tell, keep**

Then take the **union** across the patient's traits — the union, not the sum, because the same
trial often gets thrown out by more than one trait and double-counting would inflate the
result. Report the spread across the 20 patients, not one average.

Report **two ceilings**, and the second is a product idea rather than a limitation:

- **Pessimistic** — every conditional rule keeps the trial. This is what the cheap step can do
  from a plain patient description.
- **Optimistic** — conditional rules resolve as though the extra detail were available. The gap
  between the two answers a real design question: *if the system asked the coordinator two
  follow-up questions, how much more could it throw out?*

**Cost: nothing.** It is arithmetic over a file already on disk.

*Deciding number — reasoned.* Pessimistic ceiling below **40%** with six traits → no design on
the table reaches the 70% target, the honest answer is "tidy-field filter plus read
everything," and the project should stop here and say so. Between 40% and 70% → continue, but
the write-up must lead with the ceiling rather than with the model.

*Known limit:* only two traits are labelled, so only two filters can be combined today. Step 5
labels four more, after which this measurement should be re-run. Run it now anyway, because
even the two-trait version tells you whether per-trait throwing-out is nearer 5% or 20%.

### Step 3 — Can we tell that two different wordings mean the same thing? (half a day, ~$1)

**The second thing that could kill it cheaply.**

The patient's description says "carbo/pemetrexed". A trial says "previous platinum-based
chemotherapy". Those are the same thing, and the cheap step is useless if it can't tell. Worse,
matching too loosely is *dangerous*: Step 1's own analysis merged "bone metastases" into "brain
metastases" at one setting — one letter apart, clinically unrelated — and in this design that
mistake would wrongly throw out a good trial.

**Method.** Step 1 already recorded every wording this text uses for each trait, with counts and
quotes — that is the test material, no labelling needed. The invented patients in
`data/fake_patients.md` already contain deliberately different wordings for the same traits, and
that file lists them in a table at the end.

Compare three ways of deciding whether a patient wording and a trial wording mean the same
thing:

1. **Off-the-shelf meaning-numbers** — turn both short phrases into numbers and compare.
2. **A curated medical dictionary.** These exist, are free or free for research, and list for
   each medical concept every known way of saying it plus what broader category it belongs to.
   That second part is the valuable bit: it can connect a specific drug to its drug family
   without any guesswork, which is exactly the "carbo/pemetrexed" problem.
3. **Both together**, with the dictionary tried first and meaning-numbers as a fallback.

Report, for each: how often it correctly links two wordings of the same trait, and — separately
and more importantly — **how often it wrongly links two different traits**, since that is the
error that loses good trials.

*Deciding number — a guess.* Wrongly linking different traits more than **5%** of the time on
the best method → matching is the weak point and must be fixed before anything else is built.
Correctly linking the same trait under **85%** → the cheap step will miss rules, making the
shortlist bigger but not wrong; note it and continue.

*Practical note:* the medical dictionary needs registering and installing. **Give it half a day
and no more.** If it fights back, record that and carry on with meaning-numbers only; the
dictionary then becomes a possible improvement later rather than a dependency.

### Step 4 — Can the big model take a patient description apart correctly? (half a day, ~$1)

Everything downstream assumes a patient description can be turned into a clean list of traits.
Nothing has tested it — Step 1 pulled traits out of *trials*, which is the opposite direction.

Feed each of the 20 invented patient descriptions to the big model and ask for the trait list
described in Part 3, including whether each trait is a category or a number. Will then checks
all 20 against the structured answers already written in `data/fake_patients.md`, counting four
kinds of mistake separately:

- **Missed** a trait the description states.
- **Invented** one it does not state.
- **Put a direction or a number into the name** — recording "must have had chemotherapy" rather
  than "previous chemotherapy". This breaks the search step.
- **Labelled a number trait as a category**, or the reverse.

This check is careful reading of English against a list. It needs no medical knowledge: the
correct answer is already written down beside each patient.

*Deciding number — a guess.* Missed or invented traits in more than **2 of 20** → fix the
instructions once, measure once more, and say in the write-up that it was revised. More than
**4 of 20** after one revision → stop.

### Step 5 — Label four more traits (half a day, ~$14, needs approval)

The answer key covers two traits. Two cannot show whether throwing-out multiplies across
traits, which is the mechanism Part 2's arithmetic depends on.

Extend the existing instructions to four more traits and run the existing script over all 1,308
trials. Apply the same quote check as before and report how many rows it flags. Then **re-run
Step 2** with six traits instead of two.

**Four traits, two of each kind.**

*Plain yes-or-no, which the existing eight verdicts already handle unchanged:*

- previous platinum chemotherapy
- autoimmune disease

*One-of-many, which need a slightly different answer recorded:*

- **which genetic marker the trial asks for.** Record, per trial, the list of markers it
  requires and the list it refuses. Then the check is whether the patient's marker is in the
  required list. **This is the highest-value trait in the whole spike** — most trials in this
  disease are built around one particular marker, so a trial asking for a marker the patient
  doesn't carry is the commonest reason a patient is ineligible.
- **which disease stages the trial accepts.** Same shape: a list of stages allowed, checked
  against the patient's stage.

All four appear in Step 1's list of the 40 commonest traits and in the invented patients. Exact
definitions and the record shapes are in Part 11.

**Why a list rather than one verdict, and the cheaper choice.** There are two ways to handle a
one-of-many trait. You could treat every individual marker as its own yes-or-no trait — "has
marker A", "has marker B" — which needs no new machinery at all, but if the text mentions thirty
markers that is thirty separate labelling runs and thirty times the cost. Or you record one
answer per trial holding the list of markers it asks for, which is a single run. **Use the
list.** It is one labelling pass instead of thirty, and the comparison is just "is the patient's
value in this list".

**Then re-run Step 2** with six traits instead of two, since the ceiling measurement only becomes
meaningful once the strongest filter is included.

### Step 6 — Build the training material (1 day, ~$12, needs approval)

For each of the six traits, find the candidate lines across all trials, pair each with an
invented patient's situation, and have the big model label the combination **throw out / keep /
can't tell**.

This is teaching a small model to copy a big one, so **the small model can never be better than
this labelling.** Record exactly which model and which instructions produced it.

Write the three split files — train, tune, test — and commit them **before** any training runs.
Hold back one whole trait and all lines from a set of trials.

### Step 7 — Train and test the small model (1 day, ~$3)

The most technical step, so it is specified rather than described.

**Start from a model that has already been trained to spot contradictions between two
sentences.** This is the most important choice here. Our task — does this rule contradict this
patient's situation — is that same task in different clothes, and a model that already knows how
negation works arrives most of the way there. Starting from a plain model means learning
negation from 15,000 clinical examples, which will not be enough.

**How to present each example.** The model takes two pieces of text:

- **First piece — the patient's situation as an ordinary sentence.** *"The patient has previously
  received platinum-based chemotherapy."* Not a bare label and a tag. Write a sentence, because
  the model we're starting from was trained on sentences, and writing sentences is how we inherit
  its handling of negation.
- **Second piece — the trial's rule word for word, with which list it came from in front of it.**
  *"From the trial's cannot-join list: Patients with untreated brain metastases."* Include the
  list, because direction often depends on it — but the model must not treat it as the answer,
  since the first spike found lines like "No previous immunotherapy" sitting in the *can-join*
  list and functioning as a refusal.

**Expect the answers to be badly lopsided, and handle it.** A candidate line is anything
related, and most related rules will not exclude this particular patient, so "keep" will
probably be 70–85% of examples. Two consequences: weight the training so the rare answers count
properly, and **never report plain accuracy**, which would look excellent while the model failed
at the only decision that matters. Report how it does on each of the three answers separately.

**Training settings** as a starting point, to be logged and changed with reasons: batches of 16
to 32, learning rate 2e-5, three passes over the data, mixed precision, stop when the tune split
stops improving. On roughly 15,000 examples this is 15 to 25 minutes on one rented graphics card,
so a couple of dollars. Will's computer has no suitable graphics card — rent one (there is
already a key in `.env`) and **shut it down when the run finishes.** Testing runs fine on an
ordinary processor.

**How the confidence setting and the curve are produced.** The model gives each answer a
probability. Take the probability of "throw out" and try a series of settings — 0.5, 0.6, 0.7,
0.8, 0.9, 0.95 — throwing a trial out only when some line clears the setting. Each setting gives
one "share thrown out" and one "share wrongly thrown out"; plotted together those points are the
curve, and the operating point is picked off it. **Pick it on the tune split, then apply that one
setting to the test split once.** Note that these probabilities are usually overconfident, so 0.9
does not mean 90% right; a standard correction fitted on the tune split is cheap and worth doing
first.

**Three comparisons, so the training can be judged:**

1. **The same starting model with no training at all.** If training doesn't beat this, it added
   nothing.
2. **The big model** on the same test examples — the ceiling a copied model is chasing.
3. **A cheap rented model** on the same test examples. Part 2 says it is too expensive to use
   this way; this checks whether it is at least good enough, for the record.

Report all of the following, separately for held-back trials and for the **held-back trait**:
share wrongly thrown out; share thrown out; the curve between them; and a breakdown by rule
difficulty — plain refusals and requirements against the conditional ones, where the mistakes
will concentrate.

*Deciding number — reasoned from Part 2.* Wrongly throwing out more than **5%** on the held-back
trait → the small model cannot be the cheap step, because that leaves 74% of joinable trials
across six traits and gets worse fast. Between 2% and 5% → usable, and the write-up quotes the
multiplied figure, not the per-trait one.

*Deciding number — a guess.* Throwing out less than **40%** at an acceptable error rate → not
worth the complexity; the honest answer is read everything. 70% is the target.

*Deciding number — reasoned.* Wrongly throwing out more than **twice** as often on the held-back
trait as on trained traits → the model has memorised particular traits rather than learned how
direction works, which makes it the fixed-spreadsheet design Step 1 ruled out. Report it that
way and do not present the trained-trait numbers as the result.

### Step 8 — Run the whole thing, and cost it out (half a day, ~$19, needs approval)

Run all 20 invented patients through stages 1, 2 and 3 — including the read-everything baseline
from question one, which is what everything gets compared against. Use the cheaper model for
most of it and the big model on a few, so both are measured.

Record per patient: trials left after each stage, final shortlist size, total cost, elapsed
time, and how many joinable trials survived, judged against the answer key. Then project cost
and time at three sizes — 1,308 lung trials, about 124,000 cancer trials, all 604,566 — from the
measured per-trial rates.

*Deciding number — a guess.* Joinable trials surviving below **70%** → find the stage losing
them, and expect it to be stage 2. Total cost above the read-everything baseline at 1,308 trials
→ the cheap step only pays at larger sizes, which is a perfectly reportable finding.

### Step 9 — Check the answer key as far as it can be checked (90 minutes, free)

Everything above is measured against a key no human has verified.

Sample **40 trials from the rows where the key is least sure** — the 22 `both_classifications`
and 12 `unclear` on the immunotherapy trait, the 7 and 7 on the brain trait, and a sample of
`barred_with_exception`.

**Will checks only what can be checked by reading.** For each, the question is: does the quoted
sentence say what the label claims, in plain English? "Patients with brain metastases are
excluded" labelled `barred` is checkable by anyone. Where the check would need medical knowledge
— whether one medical term falls under another — **record it as unresolvable and move on.** Report
three counts: agrees, disagrees, and needed medical knowledge.

*Deciding number — a guess.* Disagreement above **25%** of the checkable ones → rework the
labelling instructions and redo the key before quoting anything that depends on it.

**Honest limitation to state in the write-up:** the share needing medical knowledge is the part of
the answer key nobody in this project can verify. Report that share rather than hiding it.

### Step 10 — Write it up

`docs/spike2_memo.md`, in the plain style of `report.md`: every number against the deciding
numbers as they were committed, with ranges; which deciding numbers turned out to be badly
chosen; total spend; and a recommendation — **go / adjust, and exactly how / stop.** It has to
stand on its own for someone who has read none of this, and be worth showing even if the answer
is stop.

⛳ **Points where Claude reviews:** after Step 2 and Step 3 together, after Step 7, and on the
write-up.

---

# Part 9 — Cost

| Step | Estimate |
|---|---|
| 2 — best-possible ceiling | $0 |
| 3 — matching different wordings | ~$1 |
| 4 — taking patient descriptions apart | ~$1 |
| 5 — labelling four more traits | ~$14, needs approval |
| 6 — training material | ~$12, needs approval |
| 7 — training and testing the small model | ~$3 |
| 8 — whole pipeline plus the read-everything baseline | ~$19, needs approval |
| 9, 10 — key check and write-up | $0 |
| **Total** | **~$50** |

**The first three steps cost about $2 between them and two of them can end the project.** Run
those before spending anything else.

# Part 10 — What would make Will stop

- **Step 2:** too many rules are written conditionally, so even a flawless cheap step cannot
  throw out enough. Nothing can fix this, because it is a property of the text.
- **Step 3:** different wordings of the same trait cannot be matched reliably, or worse, different
  traits get matched to each other.
- **Step 4:** patient descriptions cannot be turned into clean trait lists.
- **Step 7:** the small model wrongly throws out joinable trials too often, or only works on the
  traits it trained on, or barely throws anything out.

**None of these kills the project.** Every one of them lands on the same fallback: a tidy-field
filter plus the big model reading everything, which Part 1 shows costs about $9 per patient at
this size and works. That is a real product and an honest write-up.

What it is *not* is a project containing a hosted number-database and a trained retrieval
component. If the measurements say so, the write-up says so, rather than keeping parts the
evidence doesn't support.

---

# Part 11 — Specifics the coding agent needs

Everything here is concrete enough to act on. Where Claude could not verify something, it says
so — **verify and log what actually works rather than trusting a name in this document.**
Claude's knowledge of package versions and service details may be out of date.

## The environment, which is thinner than it looks

Checked 2026-09-29: **Python 3.9.12 in Anaconda base, no virtual environment, and only numpy
installed.** No torch, no transformers, no spaCy. Existing scripts use only `urllib`, `json` and
`numpy`, so nothing has needed more until now.

- **Make a virtual environment** and write a pinned `requirements.txt`. Do not install into the
  Anaconda base environment.
- **Check whether Python 3.9 is new enough** for the packages Step 7 needs. Several
  machine-learning libraries now require 3.10 or later. If it isn't, create the environment on a
  newer Python and log that decision.
- Steps 2, 3, 4, 5 and 6 need very little. Only Step 7 needs the heavy install, so defer it.

## Exact file shapes, verified

**`data/nsclc_recruiting.jsonl`** — one trial per line:
`nct_id`, `brief_title`, `overall_status`, `phases`, `conditions`, `minimum_age`,
`maximum_age`, `sex`, `healthy_volunteers`, `eligibility_criteria`.

**`data/answer_key.jsonl`** — one trial per line: `nct_id`, `brief_title`, `usage`, `checks`, and
`answer`, which contains exactly:
`prior_immunotherapy_classification`, `prior_immunotherapy_quote`,
`brain_metastases_classification`, `brain_metastases_quote`, `note`.

So the pattern for a new trait is `<trait_key>_classification` and `<trait_key>_quote`. Keep it.

**`data/fake_patients_draw.json`** — `seed`, `n`, `draw_constraints`, `patients`. Each patient has
`id`, `age`, `sex`, `disease_stage`, `histology`, `driver_mutation`, `ecog`,
`prior_immunotherapy` (true/false), `prior_platinum_chemo` (true/false),
`prior_lines_of_therapy`, `brain_metastases` (true/false), `brain_mets_treated_stable`
(true/false/null), `creatinine_clearance`, and boolean flags for `autoimmune_disease`,
`interstitial_lung_disease`, `hepatitis_b`, `hepatitis_c`, `hiv`,
`recent_myocardial_infarction`, `major_surgery_within_4_weeks`, `pleural_effusion`.

**Mapping for Step 2**, patient field to answer-key field:

| Patient field | Answer-key field |
|---|---|
| `prior_immunotherapy` | `prior_immunotherapy_classification` |
| `brain_metastases` | `brain_metastases_classification` |
| `prior_platinum_chemo` | `prior_platinum_chemo_classification` *(after Step 5)* |
| `autoimmune_disease` | `autoimmune_disease_classification` *(after Step 5)* |
| `driver_mutation` | `required_markers` and `refused_markers` *(after Step 5, list-shaped)* |
| `disease_stage` | `allowed_stages` and `refused_stages` *(after Step 5, list-shaped)* |

**`data/step1_concentration.json`** — `decision_cut`, `embed_model`, `n_trials`, `variants`
(keyed `exact_merge`, `cosine_0.9`, `cosine_0.85`, `cosine_0.8`, `cosine_0.75`), and
`discriminating_only_cosine_0.85`. Each variant holds `n_facts`, `n_clusters`, `coverage`,
`trials_fully_inside_top40`, `mean_facts_per_trial`, and a `top40` list.

**Important gap:** `top40` entries are only `{concept, count}`. **The groups of different wordings
that were merged together were never saved.** Step 3 needs them, so regenerate them from
`data/step1_concepts.jsonl` — the `merge()` function in `scripts/step1_analyze.py` does the
clustering, and the vectors are cached in `data/step1_concept_vecs.npz`. Write the groups out to
a file this time.

## Code worth reusing rather than rewriting

- **`scripts/mini_pilot.py`** holds `MODEL = "gpt-5.4"`, the prices
  (`INPUT_USD_PER_MILLION = 2.50`, `OUTPUT_USD_PER_MILLION = 15.00`), the `ask()` request
  helper, `load_key()`, and the quote checker. It also holds the labelling instructions the
  existing answer key was built with — **extend those, do not rewrite them**, or the four new
  traits will be labelled to a different standard than the two old ones.
- **`scripts/label_corpus.py`** is the threaded, resumable runner: six workers, one JSON line per
  trial, restartable after a stop. Reuse it for Step 5.
- **`scripts/step1_analyze.py`** holds the embedding call, the vector cache, and the greedy
  clustering.

Use the same model, `gpt-5.4`, wherever "the big model" appears, so nothing is compared across
different models by accident.

## Step 3 — the medical dictionary

Two options, in order of preference:

1. **UMLS**, from the US National Library of Medicine. The large one. Free, but you register and
   accept a licence, and the download is big. Python access via **`scispacy`** with its entity
   linker, or **`QuickUMLS`**. This is the one worth having, because it carries both the synonym
   lists and the hierarchy that connects a specific drug to its drug family.
2. **MeSH**, also from the same library. Smaller, freely downloadable with no licence step, and it
   has the hierarchy. A reasonable fallback if UMLS registration is slow.

For the comparison arm, use **`text-embedding-3-small`**, the same embedding model already used
elsewhere in this project, so results stay comparable.

**Claude could not verify current package names, versions, or whether they work on Python 3.9.**
Check, and if the install fights back, stop at the half-day limit, record what failed, and run
Step 3 with embeddings only.

## Step 4 — the shape of the output

Ask for exactly this, and enforce it:

    {"patient_id": "P01",
     "traits": [
       {"name": "previous platinum chemotherapy", "kind": "yes_no",
        "situation": "has", "value": null},
       {"name": "cancer spread to the brain", "kind": "yes_no",
        "situation": "has", "value": null},
       {"name": "genetic marker the tumour carries", "kind": "one_of_many",
        "situation": "value", "value": "EGFR L858R"},
       {"name": "disease stage", "kind": "one_of_many",
        "situation": "value", "value": "IV"},
       {"name": "performance status score", "kind": "number",
        "situation": "value", "value": "1"}]}

`kind` is `yes_no`, `one_of_many`, or `number`. `situation` is `has`, `does_not_have`, or
`value`. `name` carries no direction word and no number — that is what Step 4 counts as a
failure.

**On the one-of-many entries:** the model records the value the patient has, and nothing about
the values they don't. Do **not** ask it to list the alternatives the patient lacks — there may
be dozens, and the comparison handles it. The instructions do have to say that these fields are
exclusive, so that a patient recorded as carrying one marker is understood not to carry another.

## Step 5 — definitions for the four new traits

**Claude wrote these and Will cannot check them.** They are written in the style of the existing
instructions, which already exclude two specific traps: a laboratory test result is not a
treatment history, and a drug the trial itself gives during the study is not something the patient
had before. Keep both of those principles. If a definition turns out to be wrong or ambiguous
once labelling starts, that corrupts every downstream number, so **flag disagreement rather than
guessing** and log the resolution.

- **previous platinum chemotherapy** *(plain yes-or-no)* — chemotherapy containing a platinum
  drug (cisplatin, carboplatin, oxaliplatin, nedaplatin, lobaplatin) that the person received, or
  was receiving, before joining. Chemotherapy without a platinum drug does not count. A platinum
  drug the trial itself would administer does not count.
- **autoimmune disease** *(plain yes-or-no)* — a condition in which the immune system attacks the
  body's own tissue, whether active now or in the past. Includes named examples the text gives. A
  family history alone does not count. Being on a drug that suppresses the immune system is not by
  itself an autoimmune disease, though the text often mentions both together.
- **genetic marker the trial asks for** *(one-of-many, list-shaped)* — record two lists per trial.
  `required_markers` holds every specific tumour genetic change the trial demands; leave it empty
  if the trial demands none. `refused_markers` holds every one it excludes. Use the exact names the
  trial uses, plus the general phrase if it gives one — a trial saying "any sensitising alteration
  in the EGFR gene" gets that general phrase rather than a guessed list of specific ones. If the
  trial requires simply "some actionable alteration" without naming which, record the literal
  phrase; matching will have to handle it and that is worth measuring. Attach a `condition` field
  when the requirement is qualified.
- **disease stages the trial accepts** *(one-of-many, list-shaped)* — record `allowed_stages` and
  `refused_stages`, using whatever labels the trial uses, including descriptive ones like "locally
  advanced", "metastatic", "unresectable", "early". Do not translate a description into a
  numbered stage; record what it says. Attach a `condition` field when qualified.

**Both list-shaped traits need a `condition` field** for the same reason plain traits need the
`_with_exception` verdicts: a qualified requirement cannot be settled from the patient
description alone, so it routes to "can't tell" and keeps the trial.

**Why lists rather than one verdict per marker:** the text mentions many different markers. One
yes-or-no trait per marker would need one labelling run per marker over all 1,308 trials. One
list-shaped answer covers them all in a single run, and the comparison is just checking whether
the patient's value appears in the list.

## Step 7 — the model to start from

The starting point must already be trained to judge whether two sentences contradict each other.
Candidates, to verify:

- **`cross-encoder/nli-deberta-v3-base`** — around 180 million parameters, published for exactly
  this two-sentence-judgment task, usable through the `sentence-transformers` library.
- **`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`** — same size class, trained on several
  contradiction datasets, usable through plain `transformers`.
- A medical-text model such as **PubMedBERT** as the secondary comparison mentioned in Step 7. It
  knows the vocabulary but has not been trained to spot contradictions, so it tests which of the
  two head starts matters more.

Train with `transformers`' `Trainer` or `sentence-transformers`' cross-encoder trainer, whichever
is less friction. Rent the graphics card from **Lambda** — there is already a `LAMBDA_API_KEY` in
`.env` — and **shut it down when the run finishes.**

**Claude could not verify these model names are still published or that these libraries install
on this Python version.** Check first, and if none works, say so before improvising.

## Housekeeping

- `THRESHOLDS.md` already holds Step 1's entries. **Append to it, never overwrite**, and commit
  each step's numbers before that step runs.
- `DECISIONS.md` already holds the Step 1 decision. Append.
- **The repository has no remote and `data/` is ignored by git.** Do not create a remote or push
  without asking Will.
- Report tokens and dollars at every checkpoint. Ask before any single run over about $25 —
  Steps 5, 6 and 8 are near that line.
