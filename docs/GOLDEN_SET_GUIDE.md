# Golden Set Testing Guide

The golden set is a quality assurance framework for evaluating chat responses
from the Vox Quieta API. It uses YAML-defined test cases with
machine-checkable expectations to measure whether responses meet quality
standards: citing scripture, acknowledging user situations, using the right
language, and avoiding harmful phrases.

This guide covers everything you need to use, extend, and contribute to the golden set system.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Test Cases (YAML)](#test-cases-yaml)
- [Models](#models)
- [Evaluators](#evaluators)
- [Loader](#loader)
- [Running Tests](#running-tests)
- [The `interpretation` Category](#the-interpretation-category)
- [Live Runner](#live-runner)
- [Adding New Test Cases](#adding-new-test-cases)
- [Adding a New Category](#adding-a-new-category)
- [Adding a New Evaluator](#adding-a-new-evaluator)
- [Future: Reports (PR #108)](#future-reports-pr-108)
- [FAQ](#faq)

---

## Quick Start

Run the golden set tests:

```bash
cd api
../.venv/bin/python -m pytest tests/test_golden_set.py -v
```

Or use the Makefile:

```bash
make test-backend
```

Golden set tests are marked with `@pytest.mark.golden_set`, so you can run them in isolation:

```bash
cd api
../.venv/bin/python -m pytest -m golden_set -v
```

---

## Architecture Overview

```text
api/golden_set/
├── __init__.py          # Public exports
├── models.py            # Pydantic models (inputs, expectations, scores)
├── evaluators.py        # 9 automated checks + orchestrator
├── loader.py            # YAML file loading and filtering
├── runner.py            # Mock and live runs, save/load, summary (BITB-178)
├── results/             # Saved run JSON (gitignored)
└── test_cases/          # YAML test case definitions
    ├── encouragement.yaml
    ├── verse_lookup.yaml
    ├── prayer_lookup.yaml
    ├── theological.yaml
    ├── multilingual.yaml
    ├── edge_cases.yaml
    └── interpretation.yaml

scripts/
└── run_golden_set.py    # CLI for the runner (mock or live)

api/tests/
├── test_golden_set.py          # data integrity, evaluators, interpretation rules
├── test_golden_set_runner.py   # runner + CLI (mocked HTTP transport)
└── test_golden_set_live_workflow.py  # guards for the scheduled workflow
```

**Data flow:**

1. YAML files define test cases with inputs and expectations
2. The **loader** parses YAML into `GoldenSetCase` Pydantic models
3. A response (from the real API or a mock) is evaluated by the **evaluators**
4. Evaluators produce an `AutomatedScore` with pass/fail for each check
5. Tests in `test_golden_set.py` validate data integrity and evaluator correctness
6. The **runner** (`runner.py`, `scripts/run_golden_set.py`) sends cases to a running API and
   scores the real answers with the same evaluators (see [Live Runner](#live-runner))

---

## Test Cases (YAML)

Each YAML file defines a category and a list of test cases. Here is the structure:

```yaml
category: encouragement
description: "Comfort-seeking and encouragement scenarios"
cases:
  - id: "enc-001"
    name: "Feeling anxious about work"
    input:
      message: "I've been feeling very anxious about my job lately"
    expectations:
      must_contain_scripture: true
      min_verses_cited: 1
      expected_books: ["Philippians", "Psalms", "Matthew", "1 Peter", "Isaiah"]
      must_not_contain:
        - "just pray about it"
        - "you should not feel"
      response_language: "en"
      must_acknowledge_situation: true
    tags: ["anxiety", "comfort", "workplace"]
```

### YAML Fields Reference

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (e.g., `enc-001`, `vl-003`). Convention: category prefix + number. |
| `name` | Yes | Human-readable name for the test case. |
| `category` | No | Inherited from the file-level `category` if omitted. |
| `input.message` | Yes | The user message sent to the chat API. |
| `input.conversation_history` | No | Prior messages for multi-turn tests (list of `{role, content}` dicts). |
| `input.include_search` | No | Whether to include scripture search (default: `true`). |
| `input.preferred_translation` | No | Bible translation code (e.g., `kjv`, `ita1927`). |
| `input.language` | No | UI language code sent to the API as `language` (e.g., `de`). Overrides server-side language detection, as the apps do. The live runner sends it; the field is documentation only for the pure evaluators. |
| `expectations` | Yes | Machine-checkable criteria (see below). |
| `reference_response` | No | An ideal response for human comparison. |
| `tags` | No | Free-form labels for filtering (e.g., `["grief", "comfort"]`). |

### Expectations Fields

| Field | Default | Description |
|-------|---------|-------------|
| `must_contain_scripture` | `true` | Response must include Bible verse references (e.g., "John 3:16"). |
| `min_verses_cited` | `0` | Minimum number of verse references required. |
| `expected_books` | `[]` | At least one of these books must appear in the response. |
| `must_not_contain` | `[]` | Phrases that must NOT appear (case-insensitive). |
| `must_contain` | `[]` | Phrases that must ALL appear (case-insensitive). |
| `must_contain_any` | `[]` | Groups of alternatives: one alternative from EVERY group must appear (case-insensitive). See [The `interpretation` Category](#the-interpretation-category). |
| `response_language` | `"en"` | Expected language code (`en`, `it`, `de`, ... any of the 11 UI languages). |
| `source_statement_required` | `false` | Response must state whether the content is from the Bible. |
| `source_is_biblical` | `null` | If set, checks for biblical (`true`) or non-biblical (`false`) source attribution. |
| `must_acknowledge_situation` | `false` | Response must reference keywords from the user's message in its first 500 characters. |
| `max_response_length` | `null` | Maximum character length for the response. |

### Existing Categories

| Category | File | Count | Focus |
|----------|------|-------|-------|
| `encouragement` | `encouragement.yaml` | 8 | Comfort-seeking scenarios (anxiety, grief, loneliness, health) |
| `verse_lookup` | `verse_lookup.yaml` | 8 | Specific verse requests with source attribution |
| `prayer_lookup` | `prayer_lookup.yaml` | 8 | Prayer identification (biblical vs. non-biblical) |
| `theological` | `theological.yaml` | 8 | Doctrinal questions and theological topics |
| `multilingual` | `multilingual.yaml` | 6 | Italian and German language responses |
| `edge_cases` | `edge_cases.yaml` | 4 | Off-topic, adversarial, and boundary inputs |
| `interpretation` | `interpretation.yaml` | 81 | Who or what a verse refers to; stability under pushback (BITB-178) |

**Total: 121 test cases across 7 categories.** (`theological` has 6 cases, not 8.)

---

## Models

All models are defined in `api/golden_set/models.py` as Pydantic `BaseModel` classes.

### GoldenSetInput

The user input for a test case:

```python
class GoldenSetInput(BaseModel):
    message: str                              # User's chat message
    conversation_history: list[dict] = []     # Prior messages (multi-turn)
    include_search: bool = True               # Enable scripture search
    preferred_translation: str | None = None  # e.g., "kjv", "ita1927"
    language: str | None = None               # UI language code sent to the API (BITB-178)
```

### Expectations

Machine-checkable criteria for evaluating a response:

```python
class Expectations(BaseModel):
    must_contain_scripture: bool = True
    min_verses_cited: int = 0
    expected_books: list[str] = []
    must_not_contain: list[str] = []
    must_contain: list[str] = []
    must_contain_any: list[list[str]] = []    # one alternative from EVERY group (BITB-178)
    response_language: str = "en"
    source_statement_required: bool = False
    source_is_biblical: bool | None = None
    must_acknowledge_situation: bool = False
    max_response_length: int | None = None
```

### GoldenSetCase

A complete test case loaded from YAML:

```python
class GoldenSetCase(BaseModel):
    id: str
    category: str
    name: str
    input: GoldenSetInput
    expectations: Expectations
    reference_response: str | None = None
    tags: list[str] = []
```

### AutomatedScore

Result of running all automated evaluators on a response:

```python
class AutomatedScore(BaseModel):
    passed: bool            # True if all checks passed
    total_checks: int       # Number of checks run (currently 9)
    passed_checks: int      # Number of checks that passed
    failed_checks: list[str] = []  # Names of failed checks
    details: dict = {}      # Check name -> detail message
```

### HumanScore

Optional human reviewer scores (1-5 scale):

```python
class HumanScore(BaseModel):
    relevance: int = Field(ge=1, le=5)
    scripture_accuracy: int = Field(ge=1, le=5)
    tone_quality: int = Field(ge=1, le=5)
    source_attribution: int = Field(ge=1, le=5)
    overall: int = Field(ge=1, le=5)
    notes: str = ""
```

### CaseResult and EvalRun

Results from running a test case against the live API (written by the [runner](#live-runner)):

```python
class CaseResult(BaseModel):
    run_id: str
    case_id: str
    timestamp: datetime
    provider: str               # e.g., "ollama", "claude"
    model: str                  # e.g., "llama3:8b"
    input_message: str
    actual_response: str
    scripture_context: dict | None = None
    automated_score: AutomatedScore
    human_score: HumanScore | None = None
    response_time_ms: int = 0

class EvalRun(BaseModel):
    run_id: str
    timestamp: datetime
    provider: str
    model: str
    mode: Literal["mock", "live"]
    results: list[CaseResult]
    metadata: dict = {}
```

---

## Evaluators

The evaluator module (`api/golden_set/evaluators.py`) contains 9 independent
check functions and one orchestrator. Each check returns a
`(passed: bool, detail: str)` tuple.

### Check Functions

- **`check_scripture_presence`** - Counts Bible verse references
  (e.g., "John 3:16") using regex. Fails if count is below
  `min_verses_cited` or zero when `must_contain_scripture=True`.
- **`check_expected_books`** - Verifies at least one book from
  `expected_books` appears in the response (case-insensitive).
- **`check_forbidden_content`** - Ensures no phrase in
  `must_not_contain` appears in the response (case-insensitive).
- **`check_required_content`** - Ensures every phrase in `must_contain`
  appears in the response (case-insensitive).
- **`check_required_alternatives`** - For every group in
  `must_contain_any`, at least one alternative must appear
  (case-insensitive). Lets a case accept `1:78`, `1,78` or native digits.
  Reports the groups with no match (BITB-178).
- **`check_source_statement`** - Looks for source attribution in the
  first 500 characters. Checks for biblical patterns ("from the Bible",
  "found in scripture") or non-biblical patterns based on
  `source_is_biblical`.
- **`check_response_language`** - Uses `lingua-language-detector` to
  verify the response language. Gracefully skips if unavailable (this
  is the case in the scheduled live workflow, which installs only the
  runner's dependencies).
- **`check_response_length`** - Checks that response length doesn't
  exceed `max_response_length`.
- **`check_situation_acknowledgment`** - Extracts keywords (>3 chars,
  excluding stop words) from the user's input and checks that at least
  one appears in the first 500 characters of the response.

### Orchestrator

`run_all_checks(response, expectations, input_message="")` runs all 9 checks and returns an `AutomatedScore`:

```python
from golden_set.evaluators import run_all_checks
from golden_set.models import Expectations

expectations = Expectations(
    must_contain_scripture=True,
    min_verses_cited=1,
    expected_books=["Philippians"],
    must_not_contain=["just pray about it"],
    must_acknowledge_situation=True,
)

score = run_all_checks(
    response="I understand your anxiety. Philippians 4:6-7 says...",
    expectations=expectations,
    input_message="I'm anxious about work",
)

print(score.passed)         # True/False
print(score.failed_checks)  # ["scripture_presence", ...] if any failed
print(score.details)        # {"scripture_presence": "found 1 scripture references", ...}
```

---

## Loader

The loader module (`api/golden_set/loader.py`) handles YAML parsing and filtering.

### Loading Test Cases

```python
from golden_set.loader import load_test_cases

# Load all cases from the default directory (golden_set/test_cases/)
cases = load_test_cases()
print(f"Loaded {len(cases)} test cases")  # 121

# Load from a custom directory
from pathlib import Path
cases = load_test_cases(Path("/path/to/custom/test_cases"))
```

### Filtering

```python
from golden_set.loader import filter_by_category, filter_by_tags, get_case_ids

cases = load_test_cases()

# Filter by category
encouragement = filter_by_category(cases, "encouragement")

# Filter by tags (returns cases that have ANY of the given tags)
comfort = filter_by_tags(cases, ["comfort", "grief"])

# Get all case IDs
ids = get_case_ids(cases)  # ["enc-001", "enc-002", ...]
```

---

## Running Tests

### All Golden Set Tests

```bash
cd api
../.venv/bin/python -m pytest tests/test_golden_set.py -v
```

### By Marker

```bash
# Only golden set tests
../.venv/bin/python -m pytest -m golden_set -v

# Exclude golden set tests
../.venv/bin/python -m pytest -m "not golden_set" -v
```

### Specific Test Class

```bash
# Only evaluator tests
../.venv/bin/python -m pytest tests/test_golden_set.py::TestScripturePresenceCheck -v

# Only data integrity tests
../.venv/bin/python -m pytest tests/test_golden_set.py::TestYamlDataIntegrity -v
```

### Runner and Workflow Tests

```bash
cd api
../.venv/bin/python -m pytest tests/test_golden_set_runner.py tests/test_golden_set_live_workflow.py -v
```

The runner tests use `httpx.MockTransport`: no network, no API, no secrets.

### What the Tests Cover

The test suite (`test_golden_set.py`) is organized in these groups (counts
grow; see the file):

1. **Data Validation (8 tests)** - Verifies all YAML files parse
   correctly, case IDs are unique, required categories exist, and
   category-specific rules are enforced.
2. **Loader Tests (6 tests)** - Tests `load_test_cases()`,
   `filter_by_category()`, `filter_by_tags()`, and `get_case_ids()`.
3. **Evaluator Tests** - Tests each of the 9 check
   functions with passing, failing, and edge cases. Also tests the
   `run_all_checks()` orchestrator.
4. **Model Tests** - Tests Pydantic model construction,
   defaults, and validation (e.g., `HumanScore` rejects values
   outside 1-5).
5. **Interpretation Cases** - The rules of the next section (case count,
   language coverage, every reference parses, no vacuous groups).

---

## Adding New Test Cases

This is the most common contribution. To add a new test case:

### Step 1: Choose the Right File

Pick the YAML file that matches your case's category:

- Life situations and comfort-seeking → `encouragement.yaml`
- Specific verse requests → `verse_lookup.yaml`
- Prayer identification → `prayer_lookup.yaml`
- Doctrinal questions → `theological.yaml`
- Non-English responses → `multilingual.yaml`
- Off-topic or adversarial inputs → `edge_cases.yaml`
- Who a verse is about, or holding an answer under pushback → `interpretation.yaml`

### Step 2: Write the Test Case

Add a new entry to the `cases` list in the chosen file:

```yaml
  - id: "enc-009"
    name: "Dealing with rejection"
    input:
      message: "I keep getting rejected from jobs and feel worthless"
    expectations:
      must_contain_scripture: true
      min_verses_cited: 1
      expected_books: ["Psalms", "Jeremiah", "Romans", "Isaiah"]
      must_not_contain:
        - "just pray about it"
        - "God has a plan"
      response_language: "en"
      must_acknowledge_situation: true
    tags: ["rejection", "self-worth", "comfort"]
```

### Step 3: Follow the ID Convention

Use a prefix based on the category:

| Category | Prefix | Example |
|----------|--------|---------|
| encouragement | `enc-` | `enc-009` |
| verse_lookup | `vl-` | `vl-009` |
| prayer_lookup | `pl-` | `pl-009` |
| theological | `th-` | `th-009` |
| multilingual | `ml-` | `ml-005` |
| edge_cases | `ec-` | `ec-005` |
| interpretation | `interp-` | `interp-082` |

Find the highest existing ID in the file and increment by 1.

### Step 4: Validate

Run the data integrity tests to check your YAML:

```bash
cd api
../.venv/bin/python -m pytest tests/test_golden_set.py::TestYamlDataIntegrity -v
```

This will verify:

- The YAML file parses correctly
- Your case ID is unique
- The Pydantic model accepts all fields
- Category-specific rules are met (e.g., encouragement cases must
  have `must_acknowledge_situation: true`)

### Tips for Writing Good Test Cases

- **Be specific with `expected_books`**: List 3-5 books that are topically relevant, not just common ones.
- **Use `must_not_contain` to prevent cliches**: Add dismissive phrases
  like "just pray about it" or "everything happens for a reason".
- **Set `must_acknowledge_situation: true`** for comfort-seeking cases
  so the bot doesn't jump straight to scripture.
- **Set `source_statement_required: true`** when the user asks
  "is this from the Bible?" or mentions a specific prayer/quote.
- **Add meaningful tags**: Tags enable filtering for focused evaluation runs.

---

## Adding a New Category

### Step 1: Create the YAML File

Create a new file in `api/golden_set/test_cases/`:

```yaml
# api/golden_set/test_cases/relationships.yaml
category: relationships
description: "Relationship guidance scenarios"
cases:
  - id: "rel-001"
    name: "Marriage struggles"
    input:
      message: "My marriage is falling apart and I don't know what to do"
    expectations:
      must_contain_scripture: true
      min_verses_cited: 1
      expected_books: ["1 Corinthians", "Ephesians", "Colossians", "Proverbs"]
      must_not_contain:
        - "just pray about it"
      response_language: "en"
      must_acknowledge_situation: true
    tags: ["marriage", "relationships", "comfort"]

  - id: "rel-002"
    name: "Forgiveness"
    input:
      message: "How do I forgive someone who hurt me deeply?"
    expectations:
      must_contain_scripture: true
      min_verses_cited: 1
      expected_books: ["Matthew", "Colossians", "Ephesians", "Luke"]
      response_language: "en"
    tags: ["forgiveness", "relationships"]

  - id: "rel-003"
    name: "Loneliness"
    input:
      message: "I feel so alone, nobody understands me"
    expectations:
      must_contain_scripture: true
      min_verses_cited: 1
      expected_books: ["Psalms", "Deuteronomy", "Isaiah", "Hebrews"]
      response_language: "en"
      must_acknowledge_situation: true
    tags: ["loneliness", "relationships", "comfort"]
```

**Important**: Include at least 3 cases per category (enforced by tests).

### Step 2: Register in Tests (If Needed)

If your category should be a required category, add it to `test_golden_set.py::TestYamlDataIntegrity::test_required_categories_present`:

```python
required = {"encouragement", "verse_lookup", "prayer_lookup", "theological", "relationships"}
```

### Step 3: Add Category-Specific Validation (Optional)

If your category has rules (like "all encouragement cases must acknowledge the situation"), add a test:

```python
def test_relationships_cases_require_acknowledgment(self):
    cases = load_test_cases()
    rel_cases = filter_by_category(cases, "relationships")
    for case in rel_cases:
        if "comfort" in case.tags:
            assert case.expectations.must_acknowledge_situation, (
                f"Relationship comfort case {case.id} should require situation acknowledgment"
            )
```

### Step 4: Run Tests

```bash
cd api
../.venv/bin/python -m pytest tests/test_golden_set.py -v
```

The loader automatically discovers all `.yaml` files in the
`test_cases/` directory, so no registration is needed beyond creating
the file.

---

## Adding a New Evaluator

### Step 1: Write the Check Function

Add your function to `api/golden_set/evaluators.py`. Follow the pattern:

```python
def check_your_new_check(response: str, expectations: Expectations) -> tuple[bool, str]:
    """Check that <describe what this checks>."""
    # If the check is not applicable, return early
    if not expectations.your_new_field:
        return True, "check not required"

    # Perform the check
    if some_condition:
        return True, "check passed because <reason>"

    return False, "check failed because <reason>"
```

Rules:

- Return `(True, detail_string)` for pass, `(False, detail_string)` for fail
- Always include a skip path for when the check doesn't apply
- The detail string should explain why the check passed or failed

### Step 2: Add the Field to Expectations

If your check needs a new expectations field, add it to the `Expectations` model in `models.py`:

```python
class Expectations(BaseModel):
    # ... existing fields ...
    your_new_field: bool = False  # Default to False so existing cases aren't affected
```

### Step 3: Register in the Orchestrator

Add your check to `run_all_checks()` in `evaluators.py`:

```python
def run_all_checks(response: str, expectations: Expectations, input_message: str = "") -> AutomatedScore:
    checks = {
        # ... existing checks ...
        "your_new_check": check_your_new_check(response, expectations),
    }
    # ... rest unchanged ...
```

### Step 4: Write Tests

Add a test class to `tests/test_golden_set.py`:

```python
@pytest.mark.golden_set
class TestYourNewCheck:
    """Test your new evaluator."""

    def test_passes_when_condition_met(self):
        response = "..."
        exp = Expectations(your_new_field=True)
        passed, detail = check_your_new_check(response, exp)
        assert passed

    def test_fails_when_condition_not_met(self):
        response = "..."
        exp = Expectations(your_new_field=True)
        passed, detail = check_your_new_check(response, exp)
        assert not passed

    def test_skips_when_not_required(self):
        response = "Any response."
        exp = Expectations(your_new_field=False)
        passed, detail = check_your_new_check(response, exp)
        assert passed
```

### Step 5: Update Total Checks Count

In `test_golden_set.py::TestRunAllChecks::test_all_checks_pass`, update the assertion:

```python
assert score.total_checks == 10  # was 9, now 10
assert score.passed_checks == 10
```

---

## The `interpretation` Category

Added for BITB-178. A reported conversation asked "who is spoken of in Luke
1:79?"; the app named John the Baptist (the "he" is the sunrise from on high
of 1:78, the Messiah) and, asked "are you sure?", flipped without citing any
text. The category checks two things:

- **Referents and speakers**: who is the "he" / "you", who speaks, to whom.
  The Luke 1:79 question exists in all 11 languages; further verses (Luke
  1:76, 1:48 and 2:34, John 1:8, 1:11 and 3:30, Acts 8:34, Matthew 3:17 and
  11:3, Ruth 1:16, Psalm 23:4, 1 Samuel 17:45) in `en`, `de`, `it`.
- **Stability under pushback**: cases with `conversation_history` where the
  user challenges an answer. *User is right* (the earlier answer was wrong:
  the reply should correct itself and name the verse) and *user is wrong*
  (the reply should keep the answer kindly and show the verse). The Luke
  1:79 pair exists in all 11 languages. A bare "are you sure?" after a right
  answer is a *user is wrong* case. Capitulation and "I will be more careful"
  phrases go in `must_not_contain`.

### Writing checks with `must_contain_any`

Each inner list is one *group* of equivalent spellings or names; one
alternative from every group must appear:

```yaml
must_contain_any:
  - ["1:78", "1,78", "1.78", "verse 78"]   # cites the verse that holds the antecedent
  - ["jesus", "christ", "messiah"]         # names the right person
```

Rules (enforced by `TestInterpretationCases`):

- **No vacuous groups.** A check must not pass just because the question
  echoes it. For a single-turn case no group may already be satisfied by
  `input.message`. For a multi-turn case at least one group must not be
  satisfied by the message plus the history. (A history answer that says
  "verse 78" makes a "verse 78" group meaningless; word the history as "the
  verse before it" instead.)
- **No alternative may be a substring of a localized name of the book under
  discussion.** This is why Exodus 3:14 is not in the set: German "2. Mose"
  would satisfy an addressee check for "Mose".
- Every single-turn message, and the first user turn of every history, must
  parse to a verse reference with `utils.verse_parser.extract_references`.
  A challenge ("Are you sure?") names no verse itself: the service must
  carry the passage over from history.
- For `ar`, `ru`, `zh`, `hi`, `ko` set `must_contain_scripture: false`: the
  reference regex in `evaluators.py` is ASCII-only. Include native-digit and
  ASCII forms of the verse number in the alternatives.
- History answers are short prose in the case's language and do not quote
  scripture at length.
- Do not forbid "you are right" in a *user is wrong* case: a good answer may
  grant that verses 76-77 are about John while holding that verse 79 is about
  the Messiah.

String checks are a floor, not a proof of correct exegesis. Read the saved
answers (`actual_response` in the run JSON) before drawing conclusions. Case
wording outside `en`, `de` and `it` has not had native-speaker review.

---

## Live Runner

`api/golden_set/runner.py` and the CLI `scripts/run_golden_set.py` send cases
(including `conversation_history`, `language` and `preferred_translation`) to
a running API's `POST /api/v1/chat`, score the real answers with the
evaluators above, save an `EvalRun` as JSON and print a summary.

| Function | Description |
|----------|-------------|
| `run_mock(cases)` | Every case gets a placeholder answer. Exercises the pipeline only; the checks are expected to fail. No API needed. |
| `async run_live(cases, base_url, timeout, delay, client, headers)` | Sends each case sequentially with `httpx.AsyncClient` and scores the answer. `headers` are extra request headers (the probe header). |
| `probe_headers_from_env()` | Builds `{"X-Monitor-Probe-Secret": ...}` from `GOLDEN_SET_PROBE_SECRET`, or `None`. |
| `save_run(run, path=None)` / `load_run(path)` | Write / read a run as JSON. Default location: `api/golden_set/results/<run_id>.json` (gitignored). |
| `summarize(run)` / `print_summary(run)` | Counts and a human-readable summary. |

### CLI

```bash
# Pipeline smoke test, no API (81 cases, exit 0)
python scripts/run_golden_set.py --mock --category interpretation

# Against a local or dev API (Turnstile off)
python scripts/run_golden_set.py --base-url http://localhost:8000 --category interpretation
make golden-live BASE_URL=http://localhost:8000 CATEGORY=interpretation

# Only some cases
python scripts/run_golden_set.py --base-url http://localhost:8000 --tags pushback-user-right
python scripts/run_golden_set.py --base-url http://localhost:8000 --ids interp-001,interp-030
```

Flags: `--mock` or `--base-url URL` (one is required), `--category`, `--tags
A,B`, `--ids ID,ID`, `--output PATH`, `--delay SECONDS`, `--timeout SECONDS`
(default 120), `--fail-under RATE` (0-1, default 0).

Exit codes:

| Code | Meaning |
|------|---------|
| `0` | Ran; pass rate is not below `--fail-under`. |
| `1` | Pass rate is below `--fail-under`. |
| `2` | No case matches the filters. |
| `3` | Nothing was scorable: every request was blocked or errored. The run is still saved. |

A result is one of: *passed*, *failed* (the answer failed an automated
check), *blocked* (HTTP 403, Turnstile or the edge; says nothing about the
model) or *errored* (other HTTP error or a transport failure). Only the first
two count as measurements.

### Probe header

Production sits behind Turnstile and rate limits. A server-to-server caller
can pass them with the shared probe secret (the mechanism `prod-monitor.yml`
uses, `utils/monitor_probe.py`). Export it as an environment variable; the
runner sends it as `X-Monitor-Probe-Secret`:

```bash
export GOLDEN_SET_PROBE_SECRET='...'   # same value as the backend's monitor_probe_secret
python scripts/run_golden_set.py --base-url https://<backend> --category interpretation
```

The secret is read from the environment only, never from argv (no
`--probe-secret` flag exists), and is never printed, logged or written to the
saved run (`metadata.probe_header_sent` records only that a header was sent).

### Scheduled run

`.github/workflows/golden-set-live.yml` runs the `interpretation` category
against production every Monday at 03:37 UTC and on `workflow_dispatch`
(inputs `category`, `tags`, `fail_under`). It uses the existing
`MONITOR_PROBE_SECRET` secret and `BACKEND_URL` variable (no new secret, no
backend change), writes the summary to the job summary and uploads the run
JSON as an artifact. It is a measurement, not a gate: it never runs on pull
requests, and the job fails only when nothing could be measured (exit 3), when
no case matches (exit 2), or when a manual run sets `fail_under` above 0 and
the pass rate is lower. It is skipped with a notice when
`MONITOR_PROBE_SECRET` is not set. The workflow installs only `httpx`,
`pyyaml` and `pydantic`, so `check_response_language` skips itself there.

Usage accounting: the runner sends no `session_id`, so the chat route writes
no `sessions` row for it and the weekly report (which reads `sessions`) does
not count the run. The 81 requests still reach the LLM and appear in request
logs and OpenTelemetry request metrics. By contrast the existing monitor
probes send `session_id = "monitor-probe-<hex>"` and are counted in the weekly
report (nothing in `reports/weekly_report.py` excludes them).

Run JSON files are plain data; to compare two runs, load both with
`load_run()` and compare `summarize()` output and the per-case
`failed_checks`.

---

## Future: Reports (PR #108)

PR #108 adds a report module (`api/golden_set/report.py`) for generating markdown reports and comparing runs:

| Function | Description |
|----------|-------------|
| `generate_report(run)` | Creates a markdown report from an `EvalRun` |
| `save_report(report, path)` | Saves the report to a file |
| `generate_comparison(run_a, run_b)` | Compares two runs side by side |

**Usage (once merged):**

```bash
cd api
../.venv/bin/python -c "
from golden_set.runner import get_latest_run
from golden_set.report import generate_report, save_report
run = get_latest_run()
report = generate_report(run)
save_report(report, 'golden_set/reports/latest.md')
"
```

---

## FAQ

### How do I run just one category of tests?

Filter by tag or category in your test code, or use the loader directly:

```python
from golden_set.loader import load_test_cases, filter_by_category
cases = filter_by_category(load_test_cases(), "encouragement")
```

### Why does `check_response_language` sometimes skip?

It requires the `lingua-language-detector` package. If the package is
not installed, the check returns
`(True, "language detection unavailable, skipping")` instead of
failing. Install it with:

```bash
pip install lingua-language-detector
```

### What is `source_is_biblical` for?

It controls the source attribution check. Use it in test cases where
the user asks about a specific prayer or quote:

- `source_is_biblical: true` - The response should say the content IS
  from the Bible (e.g., "The Lord's Prayer is found in Matthew 6")
- `source_is_biblical: false` - The response should say the content
  is NOT from the Bible (e.g., "The Hail Mary is not from the Bible")
- `source_is_biblical: null` (default) - Any source statement is accepted

### How does the scripture reference regex work?

The pattern
`\b(\d\s+)?[A-Z][a-z]+(?:\s+[a-z]+)?\s+\d+:\d+(?:-\d+)?\b`
matches:

- `John 3:16` (simple reference)
- `1 Corinthians 13:4` (numbered book)
- `Psalm 23:1-6` (verse range)

It looks for a capitalized word (optionally preceded by a number), followed by chapter:verse notation.

### Can I use conversation history in test cases?

Yes. Set `input.conversation_history` to simulate multi-turn conversations:

```yaml
  - id: "ml-005"
    name: "Follow-up question"
    input:
      message: "Can you tell me more about that verse?"
      conversation_history:
        - role: "user"
          content: "What does the Bible say about love?"
        - role: "assistant"
          content: "1 Corinthians 13:4 tells us that love is patient..."
    expectations:
      must_contain_scripture: true
```

### What is `reference_response` for?

It's an optional field for storing an ideal response. It's not used by automated evaluators but can be helpful for:

- Human reviewers comparing actual vs. expected responses
- Future LLM-as-judge evaluators that compare response quality
- Documentation of what a "good" response looks like

### How do I add a test case in a new language?

Add it to `multilingual.yaml` and set the `response_language` and `preferred_translation`:

```yaml
  - id: "ml-005"
    name: "German comfort message"
    input:
      message: "Ich fühle mich einsam"
      preferred_translation: "schlachter"
    expectations:
      must_contain_scripture: true
      response_language: "de"
      must_acknowledge_situation: true
    tags: ["german", "comfort"]
```

### Where are test results saved?

Pytest runs print to the console. Runner runs (`scripts/run_golden_set.py`)
are saved as JSON in `api/golden_set/results/` (gitignored), or at
`--output`; the scheduled workflow uploads its run as an artifact. Markdown
reports (PR #108) are not implemented yet.
