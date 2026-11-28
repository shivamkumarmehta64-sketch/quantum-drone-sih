---
name: whiteboard-plan
description: "Architecture-first planning workflow (/whiteboard-plan) that produces a formal SPEC.md before any production code is written or modified."
---

# Whiteboard Plan

Use this skill when the user invokes `/whiteboard-plan` (or `/whiteboard`) or asks to design a feature, refactor, or bug fix before touching code.

For a worked reference of what a completed spec looks like, see [`examples/example-spec.md`](examples/example-spec.md).

## Workflow

### 1. Context & Boundary Scan
- Inspect the workspace structure, `README.md`, build/test configuration, and the specific modules involved.
- Identify existing conventions, module boundaries, and test runners.
- Do **not** edit any production files during this phase.

### 2. Clarify Blocking Unknowns
- If requirements or boundaries are ambiguous, ask 1–3 concise, high-leverage questions before finalizing the spec.
- State any reasonable assumptions explicitly.

### 3. Write `SPEC.md`
Create or update `SPEC.md` in the project root using this structure:

```markdown
# SPEC: <Feature / Refactor Title>

## 1. Goal & Scope
- **In Scope:** ...
- **Out of Scope (Untouched):** ...

## 2. Architecture & Data Contracts
- Types, schemas, API endpoints, or function signatures
- Dependency direction & module boundaries

## 3. Files to Touch
- `path/to/file` — <reason>

## 4. Edge Cases & Risks
- <Failure mode> -> <Handling strategy>

## 5. Atomic Implementation Steps
1. [ ] Step 1 — <single module/component> + <verification command>
2. [ ] Step 2 — <single module/component> + <verification command>

## 6. Acceptance Criteria & Verification
- Exact lint, type-check, build, or test commands that must pass
```

### 4. Mandatory Stop
- Present a concise summary of `SPEC.md` to the user.
- **Stop and ask for explicit approval** before writing or modifying any production code.
