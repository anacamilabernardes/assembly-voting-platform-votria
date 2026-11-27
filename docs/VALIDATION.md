# Validation of Increment 0.1

Date: October 7, 2026.

- Backend: 32 tests passed on SQLite, including the HTTP flow with CSRF and the interface origin.
- Migrations: check found no pending changes.
- Interface: TypeScript and Vite build passed; 30 modules bundled.
- Meeting source: commit `0a6724e7ada25b90fdf24f9dfca40056a0da0ba3` pinned; source downloaded without modifications.
- Browser: signed in as the fictional chair and confirmed attendance in the interface, with the count updating from 0/7 to 1/7 and a visual receipt. The preview was left open for experimentation.

Not run: concurrent PostgreSQL, load testing for 8,000 participants, Docker/remote CI, real institutional identity provider, WebAuthn, meeting video/LiveKit, document editing, PDF/A, ICP-Brasil, TSA, WORM, and registry validation.

This report covers the simulation increment only and does not constitute production acceptance.

## Preparation for Render deployment — October 7, 2026

- 47 Django tests passed on SQLite, including online password authentication, CSRF, secure cookies, official-use blocking, attempt throttling, and seed preservation.
- Final TypeScript/Vite build passed, including the password field on the sign-in screen.
- The deployment guide and `render.yaml` Blueprint were prepared for a single Docker service plus PostgreSQL.
- Fixed the PL/pgSQL function body syntax in the immutable-facts migration. This still requires execution on PostgreSQL.
- Added PostgreSQL tests and a Docker build to CI; these new jobs have not yet run on GitHub.
- Not run locally: Docker/Linux, PostgreSQL, or an actual Render deployment. This preparation did not create a public link.
