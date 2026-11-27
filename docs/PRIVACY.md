# Privacy notice template

This template must be reviewed by the institution's data protection officer before any real use. The interface shows the same text under **Privacy**.

**Controller.** The institution that runs the assembly is the controller of the personal data processed in Votria. Cam.Be, which provides the software, acts as processor.

**Data processed.** Name, institutional email and member number; voting and speaking rights; attendance sessions and intervals; roll-call votes; participation in secret ballots (without the choice); floor requests; proxy instruments; administrator actions; technical security records.

**Purpose and legal basis.** Convening, running and documenting assemblies under the institution's bylaws and the applicable law (in Brazil, the LGPD). The data protection officer confirms the legal basis, usually compliance with legal or regulatory obligations and the membership relationship.

**Secret ballots.** Choices are stored without any link to the voter. The minutes list who voted, never what they chose.

**Retention.** Proxy codes expire after 24 hours. Failed code attempts, idempotency receipts and session identifiers are deleted or anonymized by `apply_retention` after `VOTRIA_RETENTION_DAYS` (365 by default) from the assembly's closing. Votes, attendance and the audit trail form the record of the deliberation and are kept for as long as the institution must keep its minutes.

**Rights.** Members exercise their rights of access, correction and information with the institution's administration.

**Sharing.** No data is shared with third parties. Fonts and scripts are served from the platform itself; the Content-Security-Policy blocks external requests.
