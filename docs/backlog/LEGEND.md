# Backlog legend

The front matter at the top of every story file (`docs/BACKLOG_STORIES/BITB-NNN-*.md`, and the
older ones under `docs/DONE/`) is the single source of truth. Keys are one per line, in this
fixed order; optional keys are omitted when empty.

```yaml
---
id: BITB-NNN
status: todo
priority: P1
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
| `size`       | `XS` under 1 hr, `S` under 4 hrs, `M` 1-2 days, `L` 3-5 days, `XL` 1-2 weeks            |
| `rank`       | Optional integer; order inside a priority (lower first). Seeded 10, 20, 30...          |
| `created`    | ISO date the story was opened                                                          |
| `prs`        | PR numbers that implement the story, e.g. `[1292]`                                     |
| `follow_ups` | IDs of stories filed for points this one did not fix                                   |
| `depends_on` | IDs that must land first                                                               |
| `supersedes` | Optional single-line free text                                                         |

The story title is the file's one `# BITB-NNN: Title` heading (there is no `title` key).
Free text that used to sit in the old bold header lines (status wording, size ranges) was kept
as `**Status note:**`, `**Priority note:**` and `**Size note:**` lines under the heading.

Retired status emoji, for reading old text: todo (target), in-progress (construction),
in-review (magnifier), done (check mark), cancelled (cross mark).

Query with `make backlog` (see `docs/BACKLOG.md`); validate with `make backlog-check`.
