# Contributing to Votria

Thanks for helping improve the project. Votria is a simulation prototype, and changes must preserve its explicit demo-only status unless production requirements are separately designed and reviewed.

## Development setup

Follow the local setup in the [README](README.md). Before opening a pull request, run:

```sh
python backend/manage.py test governance --verbosity 2
cd frontend && pnpm build
```

The local SQLite database is intended for sequential development and tests. Database concurrency changes should also be checked in PostgreSQL through the configured CI workflow.

## Pull requests

- Use a focused branch and explain the problem and behavior change.
- Add or update tests for behavior changes.
- Keep migrations additive and do not edit an already-applied migration unless there is a documented reason and a safe upgrade path.
- Do not include credentials, real member information, or production data.
- Do not claim production readiness or legal validity.
- Update the README, backlog, validation record, or changelog when the change affects their content.

## Review checklist

- Authorization and domain rules are enforced by the backend.
- Vote and audit immutability and idempotency remain intact.
- Any new environment variables are documented in `.env.example`.
- UI changes remain clear about demo-only behavior.
- CI checks pass.
