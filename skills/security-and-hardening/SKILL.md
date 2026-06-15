---
name: security-and-hardening
description: Hardens code against common vulnerabilities — injection, broken auth, secret exposure, unsafe deserialization, SSRF. Use when handling user input, authentication, sessions, data storage, or any integration with untrusted/third-party systems.
---

# Security and Hardening

## Overview

Most breaches are not exotic — they're the same handful of mistakes: trusting input, leaking secrets, weak authorization, and unsafe defaults. This skill applies defense-in-depth at the points that matter. Treat all external input as hostile until validated, keep secrets out of code, enforce least privilege, and fail closed. Security is a property you build in at boundaries, not a scan you run at the end.

## When to Use

- Handling any user-supplied or third-party data
- Authentication, authorization, sessions, or password/token handling
- Data storage, queries, file handling, or deserialization
- Outbound requests to URLs influenced by user input

**When NOT to use as a blocker:** purely internal, no-untrusted-input utilities — but stay alert, since "internal only" tends not to stay that way.

## The Core Defenses

### 1. Validate and sanitize at the boundary
Untrusted input is validated and typed the moment it enters, against an allowlist where possible. Never interpolate input into queries, commands, HTML, or file paths.
```typescript
// SQL: parameterize — never string-concat
const rows = await db.query('SELECT * FROM users WHERE email = $1', [email]);
// Validate shape at the edge (zod)
const Body = z.object({ email: z.string().email(), age: z.number().int().min(0).max(150) });
const { email, age } = Body.parse(req.body);
```
```python
# SQL: bound parameters, never f-strings
cur.execute("SELECT * FROM users WHERE email = %s", (email,))
# Validate at the edge (pydantic)
class Body(BaseModel):
    email: EmailStr
    age: int = Field(ge=0, le=150)
```

### 2. Keep secrets out of code
No keys, tokens, or passwords in source, logs, error messages, or version control. Read from environment/secret manager. Scrub secrets from logs and from anything persisted (see `memory-and-context`, which already forbids storing secrets).

### 3. Authenticate, then authorize — every time
Check authorization on every protected action, server-side, against the *current* user — never trust a client-supplied role or ID. Guard against IDOR: confirm the user owns the resource they're addressing.
```python
task = get_task(task_id)
if task.owner_id != current_user.id:      # authorize the object, not just the route
    raise Forbidden()
```

### 4. Safe defaults, fail closed
Deny by default and open deliberately. On error, fail to the safe state (reject), not the permissive one. Hash passwords with a slow algorithm (bcrypt/argon2), set `HttpOnly`/`Secure`/`SameSite` on session cookies, and encode output for its context to prevent XSS.

### 5. Guard outbound and deserialization paths
Don't fetch user-supplied URLs without allowlisting (SSRF). Don't deserialize untrusted data into executable objects (no `pickle`/unsafe YAML on untrusted input, no `eval`). Pin and audit dependencies.

## Checklist

For the full pre-merge list (OWASP-aligned: injection, auth, access control, crypto, SSRF, logging, dependencies), see `references/security-checklist.md`.

## Red Flags

- User input concatenated into SQL, shell commands, HTML, or paths
- Secrets in source, logs, or committed files
- Authorization checked on the route but not on the object (IDOR)
- Client-supplied role/permission trusted server-side
- Passwords stored with a fast hash or, worse, plaintext
- Fetching arbitrary user-provided URLs server-side
- Errors that fail open (grant on failure) instead of closed

## Verification

- [ ] All untrusted input validated/sanitized at the boundary
- [ ] Queries parameterized; output encoded for its context
- [ ] No secrets in code, logs, or version control
- [ ] Authorization enforced server-side, per-object, against the current user
- [ ] Passwords/tokens hashed with a slow algorithm; cookies hardened
- [ ] No unsafe deserialization or unguarded SSRF paths
- [ ] Security checklist reviewed for the change
