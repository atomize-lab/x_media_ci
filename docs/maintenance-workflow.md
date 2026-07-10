# Repository Maintenance and AI-Assisted Review Policy

> Status: adopted maintenance policy
>
> Recorded: 2026-07-11
>
> Scope: `atomize-lab/citeseal`

## 1. Purpose

This document records how CiteSeal is maintained when external contributors claim issues and submit pull requests, how the nightly maintenance task operates, and where low-cost AI reviewers such as DeepSeek or Gemini may assist.

The goal is to combine an open contribution workflow with evidence-based maintainer control:

- contributors implement claimed, self-contained work;
- Hermes performs routine triage, deterministic verification, review, and low-risk repository maintenance;
- auxiliary models provide bounded second-pass checks;
- architectural, destructive, security-sensitive, and release decisions remain with the human maintainer.

AI review never replaces tests, repository policy, or maintainer judgment.

## 2. Roles and authority

### 2.1 External contributors

Contributors may:

- claim an issue and implement its acceptance criteria;
- add or update tests and documentation;
- respond to review feedback;
- revise their own pull-request branch.

A contributor does not become a repository maintainer by claiming an issue. A claim grants working ownership of that issue, not merge, release, or governance authority.

### 2.2 Hermes maintenance controller

Hermes is responsible for routine maintenance:

- fetch current GitHub state rather than relying on cached discussion;
- validate claims and assign the accepted claimant;
- detect duplicate or overlapping issues and pull requests;
- inspect diffs in isolated worktrees;
- run deterministic checks and record their real output;
- produce one consolidated maintainer review;
- request changes, close clear duplicates, and perform other reversible, low-risk actions;
- merge only when every merge gate in this document is satisfied;
- report unresolved governance decisions to the human maintainer.

Hermes must not overwrite an active contributor's implementation merely to make the pull request pass. The original author should normally receive a clear opportunity to correct it.

### 2.3 Human maintainer

The human maintainer retains final authority over:

- architecture and product direction;
- breaking API or schema changes;
- security and privacy exceptions;
- destructive repository operations or history rewrites;
- releases and publishing;
- disputed ownership or ambiguous merge decisions.

## 3. Scheduled maintenance

CiteSeal has a Hermes cron job with the following runtime configuration:

| Setting | Value |
|---|---|
| Job | `citeseal-nightly-maintenance` |
| Cron ID | `a2e1b4dc8d4d` |
| Schedule | `0 22 * * *` |
| Time | Daily at 22:00, scheduler local timezone (currently UTC+08:00) |
| Working directory | `/home/hermeslab/code-repo/projects/citeseal` |
| Delivery | Origin Telegram conversation |
| Skills | `github-issues`, `github-code-review`, `github-pr-workflow` |

The cron task is the operational authority for the schedule. This document describes policy; changing this file alone does not modify the running cron job.

### 3.1 Nightly sequence

Each run follows this order:

1. Fetch remote refs and read the current open issues, pull requests, comments, reviews, and CI/check state through authenticated GitHub access.
2. Identify changes since the previous review: new commits, claims, comments, CI results, duplicates, and inactivity.
3. Skip unchanged pull requests unless a previous blocking condition needs re-verification.
4. Create a temporary isolated worktree for every pull request requiring review.
5. Read the full diff and compare it with the issue's acceptance criteria.
6. Run deterministic checks appropriate to the changed area.
7. If the AI-review trigger rules apply, request the designated auxiliary review.
8. Independently verify useful AI findings and remove duplicates or unsupported suggestions.
9. Publish one consolidated maintainer response rather than multiple model comments.
10. Execute only permitted low-risk GitHub actions.
11. Remove temporary worktrees and confirm that the local `main` worktree remains clean.
12. Deliver a Chinese `PASS`, `PARTIAL`, or `FAIL` report. If nothing changed, explicitly report that there was no new maintenance action.

## 4. Deterministic checks are the first gate

Machine-verifiable checks run before model review. The exact command set depends on the diff, but the standard baseline is:

```bash
git diff --check
python -m pytest tests/ -v --tb=short
cd tools && python citeseal.py lint && cd ..
python tools/scripts/tweet_validate.py --root tests/fixtures/accounts
```

Rules:

- use the project's real dependency environment;
- run focused tests first when useful, followed by the full suite before merge;
- inspect CI results in addition to local results;
- never report a test as passing unless it was actually executed successfully;
- an LLM verdict cannot override a failing deterministic check;
- tests with empty bodies, tautological assertions, or assertions that can pass for unrelated errors do not satisfy the test gate.

## 5. AI-assisted rule checks

Auxiliary models are internal reviewers. They do not receive GitHub authority and do not publish comments directly.

### 5.1 DeepSeek: default low-cost rules reviewer

DeepSeek may be invoked for a pull request that has new commits or has not previously received an AI rules pass. Its checklist is:

- map every issue acceptance criterion to code, tests, or documentation evidence;
- detect accidental removal or change of existing CLI/API behavior;
- identify weak, misleading, or missing tests;
- check error paths, type boundaries, and edge inputs;
- detect unrelated scope expansion or duplicated logic;
- compare the pull-request description with the actual diff;
- identify missing documentation or migration notes.

DeepSeek produces an internal structured report containing:

- finding ID and severity;
- affected file and line/range;
- violated rule or acceptance criterion;
- evidence from the diff;
- a concrete verification or remediation suggestion;
- confidence level.

Unsupported findings are discarded. DeepSeek must not approve, request changes, close, merge, push, or edit contributor branches.

### 5.2 Gemini local router: conditional cross-file reviewer

Gemini is not run on every pull request. It is triggered when the change involves one or more of:

- substantial documentation changes;
- JSON Schema or field-reference changes;
- README, examples, specifications, and implementation that must remain mutually consistent;
- a large diff requiring long-context comparison;
- disagreement between deterministic evidence and the DeepSeek review;
- suspected omissions spanning several files.

Gemini should receive the authoritative files directly, not copied excerpts alone. Its report must list every file it actually read and compare names, types, required/optional status, commands, examples, and version claims across those files.

### 5.3 Cost and noise controls

- Do not review unchanged commits repeatedly.
- Use DeepSeek as the default low-cost pass only when there is reviewable change.
- Use Gemini only when a trigger is present.
- Do not ask both models the same generic question without a distinct review role.
- Save model output internally; publish only a deduplicated maintainer review.
- Model agreement is not proof. Every blocking finding requires code, test, schema, or policy evidence.

## 6. Issue ownership and duplicate handling

The repository follows one claimed issue to one authoritative implementation whenever practical:

1. Verify that the claim is valid and that no earlier active claim exists.
2. Assign the issue to the accepted claimant.
3. Treat that contributor's pull request as the authoritative implementation.
4. Ask other contributors not to open parallel implementations unless invited.
5. Close clear duplicate pull requests with a respectful explanation.
6. Preserve useful edge cases or test ideas from duplicates by transferring them into the authoritative review or a linked follow-up issue.
7. Merge overlapping follow-up issues into the broader active task when their acceptance criteria are already covered.

An active contributor normally gets time to respond to actionable review. Hermes may take over only when the contributor explicitly withdraws, remains inactive beyond the project's chosen response window, repeatedly cannot meet the acceptance criteria, or a release/security need makes maintainer intervention necessary.

## 7. Review and merge gates

A pull request may be merged only when all applicable gates pass:

- **Scope gate:** the implementation matches the issue and contains no unjustified unrelated work.
- **Correctness gate:** focused and full tests pass locally in the reviewed commit.
- **CI gate:** required GitHub checks pass on that commit.
- **Compatibility gate:** existing CLI, API, schema, and exit-code behavior is preserved unless an approved change explicitly says otherwise.
- **Test-quality gate:** tests fail for the intended defect and contain meaningful assertions.
- **Documentation gate:** user-visible behavior and schema changes are documented consistently.
- **Review gate:** there are no unresolved blocking review findings.
- **Mergeability gate:** the pull request is current and mergeable without unresolved conflicts.
- **Governance gate:** no architecture, security, breaking-change, or release decision is awaiting human approval.

An AI-generated `LGTM`, a contributor's claim that tests pass, or a green focused test alone is insufficient.

## 8. Permitted and prohibited automation

### Permitted without additional approval

- fetch and read repository state;
- create and remove temporary local worktrees;
- run tests, lint, validation, and read-only analysis;
- assign a verified claimant;
- add appropriate existing labels;
- publish evidence-based review comments;
- close an unambiguous duplicate with an explanation;
- merge a pull request only after all Section 7 gates pass.

### Requires human decision

- architecture or roadmap changes;
- breaking API/schema behavior;
- disputed issue ownership or ambiguous duplicate decisions;
- security/privacy exceptions;
- release creation or package publication;
- repository visibility or access changes.

### Prohibited in nightly maintenance

- force-push or history rewrite;
- delete the repository, releases, tags, or remote branches;
- expose or commit credentials;
- modify contributor branches merely to bypass review;
- claim execution, testing, or model review without real evidence.

## 9. Reporting format

Every nightly report should include:

```text
Status: PASS | PARTIAL | FAIL
Checked: issues, PRs, commits, comments, CI/checks
Deterministic evidence: commands and actual outcomes
AI review: model/route used, trigger, verified findings (or not triggered)
GitHub actions: action plus link
Waiting on contributors: explicit owner and requested change
Human decisions required: explicit question and risk
Workspace: temporary worktrees removed; main clean/dirty
```

State labels must remain precise:

- `documented` means this policy exists in the repository;
- `cron-active` means the scheduled task exists and is enabled;
- `AI-review-proposed` means rules are specified but the cron runtime has not yet been wired to invoke the auxiliary model;
- `AI-review-active` requires a real scheduled run showing model attribution and saved review evidence.

## 10. Current implementation boundary

As of 2026-07-11:

- the nightly 22:00 Hermes maintenance cron is active;
- its prompt already requires live GitHub discovery, worktree-based testing, low-risk maintenance, merge gates, cleanup, and reporting;
- this document is the authority for the DeepSeek/Gemini review policy;
- automatic DeepSeek/Gemini invocation has **not yet been wired into the cron job** and must not be described as runtime-active until a real run proves it.

A later implementation should add model invocation without weakening deterministic gates, keep each model report internal, record provider/model attribution, and verify the first scheduled run before changing the status to `AI-review-active`.
