# Changelog

## 0.2.0 — Unreleased

Product prototype for any member institution.

- Organizations with their own email domain, administrators and members; data never crosses organizations.
- Administration: CSV member import with line-level errors, assembly drafts, agenda building with roll-call, secret or election items, and publication that freezes the electorate.
- Secret ballots stored apart from voters, and elections with candidates or slates (plurality, ties elect no one, blank votes counted apart).
- Printable HTML minutes, `verify_audit` and `apply_retention` commands, privacy notice.
- Interface split into components, typed API, Portuguese and English.
- Institutional sign-in resolves the organization by email domain and binds the identity on first sign-in.
- Content-Security-Policy, self-hosted fonts, single Dockerfile, ruff, ESLint, Prettier, Playwright end-to-end tests, CodeQL and Dependabot.

## 0.1.0 — 2026-11-26

Initial public prototype release.

- Added a Django and React assembly-governance simulation.
- Implemented attendance, quorum checks, proxy authorization, agenda-based roll-call voting, speaking requests, draft minutes, and hash-linked audit events.
- Added fictional demo data, Docker/Render deployment configuration, and automated checks.
- Added Votria branding and configurable institutional email-domain and assurance-level settings.

This release is for demonstration and development only. It is not approved for official or legally binding meetings. See [Security Policy](SECURITY.md) and the [validation record](docs/VALIDATION.md).
