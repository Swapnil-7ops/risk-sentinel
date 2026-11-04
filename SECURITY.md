# Security

## Scope

This document covers the Flask application, its server-rendered UI, MongoDB Atlas data, Vercel serverless deployment, and self-hosted static assets. It does not cover customer infrastructure outside those boundaries.

## Assets and trust boundaries

Assets include credentials, sessions, users, risk and asset records, treatment mappings, audit records, and configuration secrets. Browser clients are untrusted; the Flask function is the application boundary; MongoDB Atlas and shared rate-limit storage are external trusted services; Vercel cron is an authenticated service caller.

## Threat table

| Threat | Mitigation |
|---|---|
| Spoofing | Password hashing, generic login errors, MongoDB lockout, secure session cookies, session rotation, and cron bearer secret validation. |
| Tampering | CSRF protection on state-changing routes and XHR, allowlisted typed inputs, server-side role checks, and audit records. |
| Repudiation | Audit trail records authenticated actor, action, entity, timestamp, and redacts sensitive fields. |
| Information disclosure | Strict CSP, escaped Jinja output, no-store authenticated/API responses, generic errors, and sensitive audit redaction. |
| Denial of service | Shared-storage rate limits, login lockout, bounded analytics queries, and request validation. |
| Elevation of privilege | Server-side role enforcement, TOTP MFA for admins/risk owners, active-user checks on every request, audited admin actions, forced temporary-password change, and object-level bookmark ownership checks. |

## Known residual risks

- SMTP and authenticator-app configuration are operational dependencies for email verification, password recovery, and MFA enrollment.
- MongoDB availability and rate-limit storage availability are operational dependencies.
- Cron processing is bounded by the serverless invocation duration and database availability.

## OWASP ZAP scan

Findings: _placeholder for operator results._

Fixes: _placeholder for operator remediation notes._

## Dependency audit

Audit results: `pip-audit -r requirements.txt` reported no known vulnerabilities, and `npm audit --omit=dev` reported zero vulnerabilities in production dependencies. A separate unconstrained `pip-audit` of the shared interpreter reported 129 findings in packages outside this application's declared requirements; those packages are not deployed by this project and are not included in the application audit result.

## CSRF protection review

Flask-WTF now protects every POST, PATCH, and DELETE route. The previously missing form token was `/settings/risk-appetite`; the treatment-board drag/drop flow and bookmark XHR calls now carry the CSRF token/header as well. The protected state-changing routes are registration, login, logout, password change, admin user creation, asset create/edit/delete, risk create/edit/delete, control mapping, treatment status, risk-appetite settings, and bookmark create/rename/delete.
