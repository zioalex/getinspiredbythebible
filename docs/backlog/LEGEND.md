# Backlog legend

The front matter at the top of every story file (`docs/BACKLOG_STORIES/BITB-NNN-*.md`, and the
older ones under `docs/DONE/`) is the single source of truth. Keys are one per line, in this
fixed order; optional keys are omitted when empty.

```yaml
---
id: BITB-NNN
status: todo
priority: P1
kind: feature
milestone: R1
size: M
rank: 10
created: 2026-11-13
prs: [1292]
follow_ups: [BITB-314]
depends_on: []
supersedes: free text
---
```

| Key          | Values / meaning                                                                       |
| ------------ | -------------------------------------------------------------------------------------- |
| `id`         | `BITB-NNN`, must equal the filename prefix. Allocation rules: AGENTS.md, Story IDs.     |
| `status`     | `todo`, `in-progress`, `in-review`, `blocked`, `done`, `cancelled`                     |
| `priority`   | `P0` critical/blocker, `P1` high, `P2` medium, `P3` low, `icebox` ideas for later       |
| `kind`       | What the story is for the product: `feature`, `nfr`, `fix`, `chore`, `spike` (see below). Required on open stories created from 2026-11-27 (BITB-365). |
| `milestone`  | Optional `R1`, `R2`, ...: the product release the story ships in (see below)           |
| `size`       | `XS` under 1 hr, `S` under 4 hrs, `M` 1-2 days, `L` 3-5 days, `XL` 1-2 weeks            |
| `rank`       | Optional integer; order inside a priority (lower first). Seeded 10, 20, 30...          |
| `created`    | ISO date the story was opened                                                          |
| `prs`        | PR numbers that implement the story, e.g. `[1292]`                                     |
| `follow_ups` | IDs of stories filed for points this one did not fix                                   |
| `depends_on` | IDs that must land first                                                               |
| `supersedes` | Optional single-line free text                                                         |

## Kind: what a story is for the product (BITB-365)

The commit type (`feat`, `fix`, ...) says what changed in the code and drives the version bump.
`kind` says what the change means for the product and decides where it appears in the release
notes. Pick exactly one per story; a PR implements stories of a single kind.

| `kind`    | Meaning                                                                                        | Examples                                                         | Commit types       |
| --------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------ |
| `feature` | A new capability a user can see or use                                                         | Follow-up chips on Android; topic landing pages; read aloud      | `feat`             |
| `nfr`     | A quality the user relies on without seeing it: security, privacy/legal, reliability, performance, cost, observability | Rate limits; trusted client IP; moderation failover; halfvec     | `feat`, `fix`, `perf` |
| `fix`     | Shipped behaviour is wrong and a user could notice                                              | Crisis card missed a phrasing; Arabic share image 503            | `fix`              |
| `chore`   | Development, agents, CI, tests, dependencies, docs, backlog, internal reports                    | opencode/kubeopencode, golden-set test data, weekly report       | `chore`, `ci`, `build`, `docs`, `test`, `refactor`, `style` |
| `spike`   | Research or a decision that ships nothing to users                                              | Decision records, evaluations, cost analyses                     | `chore`, `docs`    |

Only `feature`, `nfr` and `fix` appear in the product release notes. A `chore` or `spike` never uses
`feat:`/`fix:`, so agent and CI tooling stays out of the changelog users read.

When it is unclear: if a user would notice it was missing or wrong → `fix`; if they would never
notice but would be harmed without it (data leak, outage, slowness) → `nfr`.

## Milestone: the product release (BITB-365)

A release milestone (`R1`, `R2`, ...) is a GitHub milestone titled `R<n>: <outcome>`, whose
description states the outcome for users and how we know it is met. A story's `milestone` key
says which release it belongs to; `chore` stories may carry one when they are evidence the
outcome is met (e.g. a golden set). Query with `make backlog ARGS="list --milestone R1"`.

## Title and migration notes

The story title is the file's one `# BITB-NNN: Title` heading (there is no `title` key).
Free text that used to sit in the old bold header lines (status wording, size ranges) was kept
as `**Migration note (2026-11-13, status|priority|size|created):**` lines under the heading.
Migration notes are frozen 2026-11-13 context; when you change `status`/`priority`, update or delete the note.

Retired status emoji, for reading old text: todo (target), in-progress (construction),
in-review (magnifier), done (check mark), cancelled (cross mark).

Query with `make backlog` (see `docs/BACKLOG.md`); validate with `make backlog-check`.
