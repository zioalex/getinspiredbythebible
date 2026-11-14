# Product Backlog

**This file is a stable stub. Feature PRs never edit it** (CI fails a PR that does).
Since BITB-313 every story's front matter (status, priority, size, rank, PRs) lives in its
story file and is the single source of truth; the old index, which every PR used to conflict
on, is gone. The rationale is in `docs/BACKLOG_STORIES/BITB-313-conflict-free-agent-friendly-backlog.md`.

## Find stories (offline, stdlib only, small output)

```bash
make backlog ARGS="list"                                   # all open stories, one line each
make backlog ARGS="list --status in-review,in-progress"
make backlog ARGS="list --priority P0,P1 --size XS,S"
make backlog ARGS="list --grep chat"                       # id + title search
make backlog ARGS="show BITB-313"                          # path + front matter (add --full)
make backlog ARGS="list --all --format md"                 # include done, as a table
make backlog-changelog                                     # derived from git history
make backlog-check                                         # validate every story's front matter
```

Without `make`: `python3 scripts/backlog.py list|show|changelog|check|render|next-id`.
Then open the one story file you need; never read the whole backlog.

## Create, complete, cancel

- **Create:** pick the next free id (`python3 scripts/backlog.py next-id`, then also check open
  PRs per AGENTS.md -> Backlog Hygiene), add
  `docs/BACKLOG_STORIES/BITB-NNN-<slug>.md` with front matter and a `# BITB-NNN: Title`
  heading, open the PR immediately (the PR is the id claim).
- **Complete:** edit the story's front matter only: `status: done` and `prs: [N]`.
- **Cancel:** `status: cancelled` plus a one-line reason under the heading.
- **Changelog:** there is no hand-written changelog. The conventional-commit subject of the
  squash-merge (with the `BITB-NNN` id and `(#PR)`) is the entry.

## Where things moved

| What                    | Where                                                    |
| ----------------------- | -------------------------------------------------------- |
| Story status, priority  | front matter of `docs/BACKLOG_STORIES/*.md`, `docs/DONE/*.md` |
| Legend / schema         | `docs/backlog/LEGEND.md`                                 |
| Old changelog (frozen)  | `docs/backlog/CHANGELOG-archive.md`                      |
| Retrospectives, notes   | `docs/backlog/RETROSPECTIVES.md`, `docs/backlog/NOTES.md` |
| Old index and its history | `git log -- docs/BACKLOG.md` (last full version before BITB-313) |
| Rendered index          | job summary of the `backlog` workflow on every push to `main` |

## CI guard

The `backlog-stub-guard` job fails any PR whose diff touches `docs/BACKLOG.md`: move the change
into the story's front matter instead. Exemptions: the cutover PR (#1292, matched by PR number) or the
`backlog-stub-edit` label — use the label to change this stub. No workflow has write permission and no bot commits.
