# Votria

First functional increment of the assembly voting platform. The governance module uses Django and React and keeps meeting and document integrations separate from vote counting. All demo data is fictional.

## Publish an online demo

Follow the [Render guide](docs/RENDER.md). The `render.yaml` file creates one application with an interface, server, and PostgreSQL database. The online demo requires an access password, keeps DEBUG=false, uses HTTPS, and blocks official use.

## Run locally

Requirements: Python 3.12 or 3.13, a Node.js version compatible with Vite 7, and pnpm 11.

1. Create a Python environment: `python -m venv .venv`.
2. Install dependencies: `.venv/Scripts/python.exe -m pip install -r backend/requirements.txt` (Windows) or `.venv/bin/python -m pip install -r backend/requirements.txt` (Linux).
3. Apply migrations and load fictional data: `python backend/manage.py migrate` and `python backend/manage.py seed_demo`, using the environment's Python.
4. Start the backend: `python backend/manage.py runserver 127.0.0.1:8000 --noreload`.
5. In `frontend`, run `pnpm install --frozen-lockfile` and `pnpm dev`.
6. Open http://127.0.0.1:5173.

Seeding is idempotent and does not delete history. After a demo ends, the chair can start a new one. The group receives a new meeting with the same profiles and agenda items, but without votes, attendance, or proxy authorizations from the previous test.

Optional: `docker compose up --build` starts the development backend and PostgreSQL. Set random values for DJANGO_SECRET_KEY and POSTGRES_PASSWORD first. The frontend must still be started separately. This compose setup has not yet been validated in a Docker environment and is not a production deployment.

## Demo walkthrough

- Sign in as Carla, create a proxy authorization for Diego, and retrieve the code from Carla's test inbox.
- Switch to Diego, confirm attendance, and accept the code. Switching profiles ends attendance for the previous session.
- Repeat with Elisa to check the two-proxy limit. A third acceptance is rejected.
- Sign in as Ana, confirm attendance, and install the meeting in the second call. The first call requires five personally present participants out of the fictional group of seven.
- Open an ordinary agenda item. Vote, request to speak, and try the representative ballot in separate sessions.
- Prepare all required proxy authorizations before installation; issuing or accepting them is blocked after installation.
- Close voting to reveal the result and roll-call votes. The tally stays hidden until then.
- Finalize the meeting and download the structured draft minutes.
- The special motion remains blocked because no statutory rule has been configured.

For multiple simultaneous participants, use isolated browser profiles. Multiple tabs in the same profile share one identity and count as one person.

## Implemented

Persistence and migrations; fictional snapshot; session authentication with CSRF; domain validation; institutional OIDC login preparation with issuer/sub binding and MFA ACR; explicit demo attendance, 60-second leases, and consolidated intervals; first and second call; proxy authorization with random token, HMAC, encrypted delivery to a local inbox visible only to the grantor, limit of two, scope control, and revocation; precedence of a present principal; own or representative vote by agenda item; single ballot, receipt, idempotent retry, and YES > NO outcome; regular speaking queue and points of order; deterministic draft minutes; audit chaining and database triggers against vote or event changes.

Attendance and grantor confirmations in the demo are **DEMO_CONFIRMATION**, not WebAuthn or an advanced signature. Receipts have an internal hash but no institutional signature yet. JSON draft minutes are not a registry document. The local inbox does not send real email. These substitutes must not be used in an official meeting: official-use commands are unconditionally blocked.

## Validation

Run `python backend/manage.py test governance --verbosity 2` for authorization, quorum, attendance, proxy authorization, voting, deadlines, idempotency, integrity, tally privacy, and official-use blocking tests. Run `pnpm build` to check TypeScript and bundle the React application.

Local SQLite is intended only for development and sequential tests. Locks and performance for concurrent voting must be validated with PostgreSQL. This increment uses an exclusive lock per meeting as an initial correctness measure; it has not been validated for 8,000 users. Shared barriers, an outbox, a WebSocket gateway, and background jobs are listed in the [backlog](docs/BACKLOG.md).

## La Suite

The official meeting source is stored in `upstream/meet` without modifications, with its commit recorded in `upstream.lock.json`. The copy is not included in the main repository; preserve its licenses when distributing changes. Meet 1.33.0 requires Python >=3.13 and has its own environment/runtime. Do not install its dependencies into the governance module's Python environment.

This first increment does not run Meet, LiveKit, or Docs, and does not issue media tokens. The next step is to create authenticated adapters with the shared identity provider, speaker-stage grants, and a private document; never use a public room URL as proof of attendance.

## Blockers before official use

Connect and test the real identity provider and member registry; implement WebAuthn and proxy-grant ceremonies; approve the snapshot and normative rules; add dual approval for board actions and commands; implement the special-motion engine; add ICP-Brasil signatures and PDF/A; add TSA/WORM and an independent verifier; validate with the registry; deliver real email; protect against systemic attendance failures; implement pause/extension/annulment; add observability, Kubernetes/disaster recovery, and CI/CD; complete PostgreSQL concurrency, accessibility, security, and 8,000-user load testing.

Do not disable the official-meeting block until these items are completed and reviewed. DEBUG=false requires secrets and PostgreSQL. Online fictional sign-in is available only when demo mode is enabled and the demo access password has at least 16 characters; this does not enable official use.
