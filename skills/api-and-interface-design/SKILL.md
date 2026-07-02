---
name: api-and-interface-design
description: Designs stable, hard-to-misuse interfaces — REST/GraphQL endpoints, module boundaries, and type contracts. Use when creating any public interface, defining contracts between modules, or establishing the boundary between frontend and backend.
---

# API and Interface Design

## Overview

An interface is a promise. Once something depends on it, changing it is expensive — so the cost of a careless contract is paid for the life of the system. Good interfaces are small, predictable, hard to misuse, and explicit about errors. This skill applies whether the "interface" is an HTTP API, a library function, or the boundary between two modules.

## When to Use

- Designing REST/GraphQL endpoints or RPC methods
- Defining the type contract between modules or services
- Establishing the frontend/backend boundary
- Introducing any function or class others will depend on

**When NOT to use:** purely internal implementation details with a single caller that you control and can change freely. Don't over-formalize what isn't a boundary yet.

## Principles

- **Make it hard to misuse.** Required things are required by the type, not by the docs. Illegal states should be unrepresentable.
- **Small surface, deep value.** Fewer methods, fewer parameters, fewer ways to hold it wrong. Add to an interface reluctantly — you can't easily take things away.
- **Explicit errors.** Callers must know what can fail and how. Don't bury failures in null returns or generic exceptions.
- **Consistent shapes.** Same casing, same pagination, same error envelope across every endpoint. Surprise is a cost.
- **Design for evolution.** Assume v2 will come. Additive change should not break v1.

## Process

### 1. Name the contract
State inputs, outputs, error cases, and invariants before writing the implementation. Model the data so wrong states can't be expressed:
```typescript
// Illegal states unrepresentable: a task is either active (no completedAt) or done (has one)
type Task =
  | { id: string; title: string; status: 'pending' | 'active' }
  | { id: string; title: string; status: 'completed'; completedAt: Date };
```
```python
from typing import Literal
from pydantic import BaseModel

class TaskCreate(BaseModel):
    title: str            # required by the type, not by a comment
    assignee_id: str | None = None
```

### 2. Design the error model first
Decide the failure contract up front and keep it uniform:
```jsonc
// One error envelope for every endpoint
{ "error": { "code": "VALIDATION_FAILED", "message": "title must not be empty", "field": "title" } }
```
Use status codes for their meaning (400 client error, 404 missing, 409 conflict, 422 unprocessable, 5xx server). Never return 200 with an error body.

### 3. Make boundaries explicit
At a module boundary, expose the minimum. Keep internal types internal; export a deliberate public surface. Dependencies flow one direction — UI depends on services, not the reverse.

### 4. Plan versioning before you ship
Additive fields are safe. Removing or renaming is breaking. For HTTP, version when you must break (`/v2/...`); for libraries, deprecate before removing.

### 5. Validate at the boundary
Untrusted input is validated and typed the moment it crosses in — never trust the caller. See `security-and-hardening`.

## Red Flags

- A new endpoint with a different casing or error shape than its neighbors
- Booleans that should be enums ("what does `true` mean here?")
- Optional parameters that are actually required in certain combinations
- Errors returned as `null` or as a generic 500
- A "small" change that silently breaks existing callers
- Internal types leaking across a public boundary

## Verification

- [ ] Inputs, outputs, errors, and invariants are explicit in the types
- [ ] Illegal states are unrepresentable where practical
- [ ] The error model is consistent with the rest of the surface
- [ ] The change is additive, or versioned/deprecated if breaking
- [ ] Untrusted input is validated at the boundary
- [ ] The public surface is the minimum needed
