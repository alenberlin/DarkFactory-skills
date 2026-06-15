# Security Checklist (OWASP-aligned)

Companion to the `security-and-hardening` skill. Run before merging anything that touches untrusted input, auth, or data.

## Input & injection
- [ ] All external input validated against a schema/allowlist at the boundary
- [ ] SQL/queries parameterized — no string concatenation of input
- [ ] Shell/OS commands avoid interpolated input (use arg arrays, not a shell string)
- [ ] File paths validated against traversal (`../`); uploads type/size checked
- [ ] Output encoded for its context (HTML, attribute, JS, URL) to prevent XSS

## Authentication & sessions
- [ ] Passwords hashed with bcrypt/argon2/scrypt (never fast hashes or plaintext)
- [ ] Session cookies set `HttpOnly`, `Secure`, `SameSite`
- [ ] Tokens expire; refresh/rotation handled; logout invalidates server-side
- [ ] Brute-force protection (rate limiting / lockout) on auth endpoints

## Authorization & access control
- [ ] Every protected action authorizes server-side against the current user
- [ ] Object-level checks prevent IDOR (user owns the resource they reference)
- [ ] Client-supplied roles/permissions never trusted
- [ ] Default deny; privileges follow least-privilege

## Secrets & config
- [ ] No secrets in source, logs, error messages, or version control
- [ ] Secrets read from env/secret manager; rotation possible
- [ ] Debug/verbose errors disabled in production

## Data & transport
- [ ] TLS enforced; no sensitive data over plaintext
- [ ] PII minimized, encrypted at rest where required
- [ ] No unsafe deserialization of untrusted data (`pickle`, unsafe YAML, `eval`)

## Outbound & dependencies
- [ ] User-influenced outbound URLs allowlisted (SSRF guard)
- [ ] Dependencies pinned; known-vuln scan clean
- [ ] Webhooks verify signatures

## Errors & logging
- [ ] Fails closed (denies) on error, never opens
- [ ] Security-relevant events logged; secrets/PII scrubbed from logs
