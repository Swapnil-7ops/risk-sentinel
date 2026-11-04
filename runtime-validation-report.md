# Runtime Validation Report

**Generated**: 2026-11-04T12:27:00Z
**Target**: `C:\Users\swapn\OneDrive\Desktop\Risk Sentinel`

## Summary

| Step | Status | Exit Code | Details |
|---|---|---:|---|
| Startup | PASS | n/a | Flask started on `127.0.0.1:5000`; `/healthz` returned 200 |
| Python tests | PASS | 0 | 69 tests passed |
| Python compilation | PASS | 0 | `app` and `tests` compiled successfully |
| CSS build | PASS | 0 | Tailwind build completed |
| npm audit | PASS | 0 | 0 vulnerabilities |
| Declared pip audit | PASS | 0 | `requirements.txt`: no known vulnerabilities |
| Browser E2E | PASS | 0 | 3 Playwright flows passed |
| Route smoke checks | PASS | 0 | Login/register/health/404/cron/static responses matched expectations |

## Browser Flows

- Health endpoint and static CSS availability.
- Login page rendering and invalid authentication feedback.
- CSP-protected page rendering and theme-toggle state change.

## Security and Error Checks

- `/auth/login`: 200 HTML.
- `/auth/register`: 200 HTML.
- `/healthz`: 200 JSON.
- `/does-not-exist`: 404 custom HTML.
- `/api/cron/overdue` without credentials: 401 JSON.
- `/static/app.css`: 200 CSS.
- Verified CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, and Permissions-Policy.
- Browser UI tests found no stack traces.

## Environment and Gaps

- Docker: unavailable because Docker is not installed; container-backed MongoDB validation was not possible.
- Node.js: available, v22.19.0.
- Playwright: available, Chromium installed and used.
- The full environment-level `pip_audit` reported advisories in unrelated installed packages. The declared project requirements were audited separately and returned no known vulnerabilities.
- Authenticated workflows requiring a real user session and Atlas data were covered by the existing pytest suite, but were not duplicated in browser tests to avoid modifying user data.

## Verdict

```text
environment:
  docker: UNAVAILABLE — Docker is not installed
  node: AVAILABLE — v22.19.0
  playwright: AVAILABLE — Chromium installed successfully
  infra-tier: FALLBACK(embedded/in-memory) — no Docker daemon available; existing tests use controlled fixtures
  browser-tier: PRIMARY(Playwright) — 3 browser flows passed
startup: PASS — python run.py, /healthz returned 200
integration: PASS — exit_code: 0, passed: 69, failed: 0, skipped: 0
e2e: PASS — exit_code: 0, passed: 3, failed: 0, flows tested: health/static, invalid login, CSP/theme toggle
overall: PASS — application, security smoke checks, and browser validation passed; Docker-backed database testing remains unavailable
```
