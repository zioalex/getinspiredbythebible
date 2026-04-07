# Project Agents Configuration

## Workflow: Plan → Delegate → Implement → Verify

```text
User Request → Orchestrator (Plan) → Subagent (Implement via acpx_claude) → Orchestrator (Verify) → Report
```

1. **Orchestrator** receives all user requests (default entry point)
2. Orchestrator plans and decomposes into subtasks
3. Orchestrator delegates to specialist subagents via `acpx_claude`
4. Subagents implement using Minimax 2.5 free model
5. Orchestrator verifies work, ensures CI passes
6. Orchestrator reports to user

## Agents

| Agent | Model | Role |
| ------- | ------- | ------ |
| **orchestrator** | claude-opus-4.6 | High-level planner, delegates via acpx_claude, verifies work |
| android-expert | minimax-m2.5-free | Android/Kotlin implementation |
| fullstack-engineer | minimax-m2.5-free | API/Frontend/PostgreSQL implementation |
| infra-engineer | minimax-m2.5-free | Azure/Terraform/CI-CD infrastructure |
| build | free | Fallback for simple edits |
| plan | free | Fallback for planning |

## Subagent Routing

| Task Type | Delegate To |
| ----------- | ------------- |
| Android/Kotlin work | android-expert |
| API/Frontend/PostgreSQL | fullstack-engineer |
| Azure/Terraform/CI-CD | infra-engineer |
| Cross-cutting | Sequential: infra → fullstack → android |

## Delegation via acpx_claude

```javascript
acpx_claude(
  prompt="Implement [task]. Requirements: [details]. Return: [what to report]",
  session="android-expert",  // or fullstack-engineer, infra-engineer
  timeout=180,
  dryRun=false
)
```

## Self-Improvement

The Orchestrator can and should update these files to improve workflows:

- `/workspace/AGENTS.md` — Update delegation rules, add learnings
- `/workspace/opencode.json` — Adjust agent configs, prompts, models

After successful patterns emerge, codify them in these files.

## Fallback Agents

Use `build` or `plan` agents directly only for:

- Simple one-line fixes
- Quick file reads without analysis
- Short documentation writing

## CI Verification

**NEVER merge a PR without first checking that all CI checks pass.**

- Run `gh pr checks <PR_NUMBER>` or check PR status on GitHub
- Wait for all jobs (Android Lint, Unit Tests, etc.) to complete
- If CI fails, investigate and fix before merging
