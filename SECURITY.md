# Security Policy

## Supported versions

Votria is an early-stage simulation prototype. No release is approved for production or legally binding voting. The current development line is the only supported version.

## Reporting a vulnerability

Please do not report security vulnerabilities in a public issue. Use GitHub's private vulnerability reporting feature for this repository if it is available. If it is unavailable, contact the maintainers privately through the GitHub profile associated with this repository.

Include a concise description, affected version or commit, impact, and steps to reproduce. Avoid sending real member data, passwords, access tokens, or other personal information.

The maintainers will acknowledge reports when possible, assess scope and severity, and coordinate a fix and disclosure with the reporter. No response-time commitment is currently provided.

## Known limitations

Secret-ballot choices are stored apart from voters, but a database administrator with low-level access to transaction metadata could still correlate them. See the README for details.

## Safe-use limits

Do not submit real member data or use the demo for an official meeting. See the README and validation record for known limitations.
