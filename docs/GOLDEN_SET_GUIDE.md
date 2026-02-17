# Golden Set Testing Guide

The golden set is a quality assurance framework for evaluating chat responses
from the Bible Inspiration Chat API. It uses YAML-defined test cases with
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
- [Adding New Test Cases](#adding-new-test-cases)
- [Adding a New Category](#adding-a-new-category)
- [Adding a New Evaluator](#adding-a-new-evaluator)
- [Future: Live Runner (PR #107)](#future-live-runner-pr-107)
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
├── evaluators.py        # 7 automated check functions + orchestrator
├── loader.py            # YAML file loading and filtering
└── test_cases/          # YAML test case definitions
    ├── encouragement.yaml
    ├── verse_lookup.yaml
    ├── prayer_lookup.yaml
    ├── theological.yaml
    ├── multilingual.yaml
    └── edge_cases.yaml

api/tests/
└── test_golden_set.py   # 51 pytest tests for the golden set system
```

**Data flow:**

1. YAML files define test cases with inputs and expectations
2. The **loader** parses YAML into `GoldenSetCase` Pydantic models
3. A response (from the real API or a mock) is evaluated by the **evaluators**
4. Evaluators produce an `AutomatedScore` with pass/fail for each check
5. Tests in `test_golden_set.py` validate data integrity and evaluator correctness

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
| `response_language` | `"en"` | Expected language code (`en`, `it`, `de`). |
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
| `multilingual` | `multilingual.yaml` | 4 | Italian and German language responses |
| `edge_cases` | `edge_cases.yaml` | 4 | Off-topic, adversarial, and boundary inputs |

**Total: 40 test cases across 6 categories.**

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
```

### Expectations

Machine-checkable criteria for evaluating a response:

```python
class Expectations(BaseModel):
    must_contain_scripture: bool = True
    min_verses_cited: int = 0
    expected_books: list[str] = []
    must_not_contain: list[str] = []
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
    total_checks: int       # Number of checks run (currently 7)
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

Results from running a test case against the live API (used by the runner in PR #107):

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

The evaluator module (`api/golden_set/evaluators.py`) contains 7 independent
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
- **`check_source_statement`** - Looks for source attribution in the
  first 500 characters. Checks for biblical patterns ("from the Bible",
  "found in scripture") or non-biblical patterns based on
  `source_is_biblical`.
- **`check_response_language`** - Uses `lingua-language-detector` to
  verify the response language. Gracefully skips if unavailable.
- **`check_response_length`** - Checks that response length doesn't
  exceed `max_response_length`.
- **`check_situation_acknowledgment`** - Extracts keywords (>3 chars,
  excluding stop words) from the user's input and checks that at least
  one appears in the first 500 characters of the response.

### Orchestrator

`run_all_checks(response, expectations, input_message="")` runs all 7 checks and returns an `AutomatedScore`:

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
print(f"Loaded {len(cases)} test cases")  # 40

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

### What the Tests Cover

The test suite (`test_golden_set.py`) has 51 tests organized in 4 groups:

1. **Data Validation (8 tests)** - Verifies all YAML files parse
   correctly, case IDs are unique, required categories exist, and
   category-specific rules are enforced.
2. **Loader Tests (6 tests)** - Tests `load_test_cases()`,
   `filter_by_category()`, `filter_by_tags()`, and `get_case_ids()`.
3. **Evaluator Tests (31 tests)** - Tests each of the 7 check
   functions with passing, failing, and edge cases. Also tests the
   `run_all_checks()` orchestrator.
4. **Model Tests (6 tests)** - Tests Pydantic model construction,
   defaults, and validation (e.g., `HumanScore` rejects values
   outside 1-5).

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
assert score.total_checks == 8  # was 7, now 8
assert score.passed_checks == 8
```

---

## Future: Live Runner (PR #107)

PR #107 adds a runner module (`api/golden_set/runner.py`) that sends
test cases to the actual chat API and records results. Key functions:

| Function | Description |
|----------|-------------|
| `run_mock(cases)` | Runs all cases with a mock response for testing the pipeline |
| `run_live(cases, base_url)` | Sends each case to the real chat API and records responses |
| `save_run(run)` | Saves an `EvalRun` to `golden_set/results/` as JSON |
| `load_run(path)` | Loads a saved run from JSON |
| `list_runs()` | Lists all saved runs |
| `get_latest_run()` | Returns the most recent run |
| `print_summary(run)` | Prints a human-readable summary of results |

It also adds a human review CLI (`api/golden_set/reviewer.py`) for manual scoring:

| Function | Description |
|----------|-------------|
| `review_run(run)` | Interactive CLI to score each case result on a 1-5 scale |
| `review_case(result)` | Score a single case result |

**Usage (once merged):**

```bash
cd api

# Mock run (no API needed)
../.venv/bin/python -c "
from golden_set.runner import run_mock, save_run, print_summary
from golden_set.loader import load_test_cases
cases = load_test_cases()
run = run_mock(cases)
save_run(run)
print_summary(run)
"

# Live run (requires running API)
../.venv/bin/python -c "
from golden_set.runner import run_live, save_run, print_summary
from golden_set.loader import load_test_cases
cases = load_test_cases()
run = run_live(cases, base_url='http://localhost:8000')
save_run(run)
print_summary(run)
"
```

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

Currently, test results are only in pytest output. Once PR #107 is
merged, results will be saved as JSON files in
`api/golden_set/results/`. Once PR #108 is merged, markdown reports
will be in `api/golden_set/reports/`.
