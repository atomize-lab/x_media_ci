# Architecture Decision Records (ADRs)

This directory records architecture decisions that shape CiteSeal's design.

Each ADR follows the [Michael Nygard template](https://github.com/joelparkerhenderson/architecture-decision-record/tree/main/src/templates/decision-record-template-nygard):

- **Title**: A short noun phrase
- **Status**: Proposed, Accepted, Deprecated, or Superseded
- **Context**: Why this decision was needed
- **Decision**: What was decided
- **Consequences**: What follows from the decision

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-agent-bundle-as-agent-consumption-layer.md) | Agent bundle as the agent consumption layer | Accepted |
| [0002](0002-local-first-boundary.md) | Local-first boundary: capture vs. consumption separation | Accepted |

## When to write an ADR

Write an ADR when making a decision that:

- Affects the project's architecture or data model (not a bug fix or refactor)
- Is hard to reverse (changing it later would break consumers)
- Has meaningful trade-offs that future contributors should understand

Do **not** write an ADR for:

- Implementation details within a single function
- Dependency version bumps
- Test-only changes
