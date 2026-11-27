# Implementation Backlog

## Increment 1 delivered

Persistent core and simulation interface for assembly, attendance, proxy authorization, agenda items, roll-call voting, speaking requests, and draft minutes. Includes migrations and automated tests for implemented behavior.

## Increment 2: identity and evidence

Connect the member registry and institutional identity provider; implement WebAuthn ceremonies, prepared and signed instruments, encrypted SMTP/outbox delivery, and confirmation to the grantor. Validate sign-in in a real environment. Do not accept email or MFA claims supplied through self-declared headers.

## Increment 3: complete governance

Add an approved and versioned snapshot, notice and meeting preparation by the board, declarative special-motion rules, pause/extension/annulment flows, incident reconciliation, and independent command controls. Implement dual approval and challenges as specified in the product requirements.

## Increment 4: meeting and document integrations

Add a meeting UI fork, shared identity provider, LiveKit tokens and permissions, private speaker stage and audience, document integration, and controlled minutes editing. Pin the document-service commit and validate both APIs.

## Increment 5: registry-grade evidence

Add PDF/A, board signatures using ICP-Brasil, RFC 3161 timestamps, a canonicalized manifest, WORM storage, an offline verifier, circulation/objections/approval, and a validated registry profile. The current internal JSON proof format does not meet these requirements.

## Increment 6: operations

Add PostgreSQL high availability, efficient barriers, an outbox and gateway, Kubernetes, metrics, disaster recovery, CI/CD, race-condition testing, penetration testing, load testing for 8,000 participants, an association-wide simulation, and production acceptance.
