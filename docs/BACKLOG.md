# Implementation Backlog

## Increment 1 delivered

Persistent core and simulation interface for assembly, attendance, proxy authorization, agenda items, roll-call voting, speaking requests, and draft minutes. Includes migrations and automated tests for implemented behavior.

## Increment 1.5 delivered: product prototype

Organizations with their own email domain and administrators; CSV member import with line-level errors and first-login identity binding; assembly drafts, agenda building and publication that freezes the electorate; secret ballots kept apart from voters; elections with candidates or slates; printable HTML minutes; `verify_audit` and `apply_retention` commands; privacy notice; Portuguese and English interface; Content-Security-Policy and self-hosted fonts; ruff, ESLint, Prettier, Playwright end-to-end tests, CodeQL and Dependabot.

## Increment 2: identity and evidence

Connect the member registry and institutional identity provider; implement WebAuthn ceremonies, prepared and signed instruments, encrypted SMTP/outbox delivery, and confirmation to the grantor. Validate sign-in in a real environment. With several organizations, each needs its own identity provider settings and member registry connection, not only an email domain. Do not accept email or MFA claims supplied through self-declared headers.

## Increment 3: complete governance

Add an approved and versioned snapshot, notice and meeting preparation by the board, declarative special-motion rules configurable per organization, pause/extension/annulment flows, incident reconciliation, and independent command controls. Implement dual approval and challenges as specified in the product requirements.

## Increment 4: meeting and document integrations

Add a meeting UI fork, shared identity provider, rooms and documents isolated per organization, LiveKit tokens and permissions, private speaker stage and audience, document integration, and controlled minutes editing. Pin the document-service commit and validate both APIs.

## Increment 5: registry-grade evidence

Add PDF/A, board signatures using ICP-Brasil, RFC 3161 timestamps, a canonicalized manifest, WORM storage, an offline verifier, circulation/objections/approval, and a validated registry profile per country or jurisdiction (ICP-Brasil applies only in Brazil). The current internal JSON proof format does not meet these requirements.

## Increment 6: operations

Add a cryptographic secret ballot (mixnet or homomorphic tally) so that not even database administrators can link a voter to a choice. Add PostgreSQL high availability, efficient barriers, an outbox and gateway, Kubernetes, metrics, disaster recovery, CI/CD, race-condition testing, penetration testing, load testing for 8,000 participants, per-organization limits and metrics, an association-wide simulation, and production acceptance.
