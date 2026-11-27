# Changelog

## Unreleased

- Added `VOTRIA_INSTITUTION_NAME`, shown on the sign-in screen.
- Fictional demo accounts now use the configured institutional email domain, and the demo sign-in checks that domain.
- An invalid `VOTRIA_ALLOWED_EMAIL_DOMAIN` now stops startup with a clear error.
- The Render Blueprint asks for the institution name and email domain of each deployment.

## 0.1.0 — 2026-11-26

Initial public prototype release.

- Added a Django and React assembly-governance simulation.
- Implemented attendance, quorum checks, proxy authorization, agenda-based roll-call voting, speaking requests, draft minutes, and hash-linked audit events.
- Added fictional demo data, Docker/Render deployment configuration, and automated checks.
- Added Votria branding and configurable institutional email-domain and assurance-level settings.

This release is for demonstration and development only. It is not approved for official or legally binding meetings. See [Security Policy](SECURITY.md) and the [validation record](docs/VALIDATION.md).
