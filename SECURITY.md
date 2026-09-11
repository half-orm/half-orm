# Security Policy

## Reporting a vulnerability

**Please do not open a public issue.**

Use GitHub's private vulnerability reporting:
[github.com/half-orm/half-orm/security/advisories/new](https://github.com/half-orm/half-orm/security/advisories/new).
It creates a private thread with the maintainers and, if the report is
confirmed, the advisory and CVE are published from it.

If that form is unavailable to you, write to **joel.maizi@collorg.org** with
`[half-orm security]` in the subject.

Useful in a report: the halfORM and PostgreSQL versions, the shortest code
that shows the problem, and what an attacker gets out of it. A reproduction
matters more than a severity score — it is what tells a real finding from a
theoretical one, and what makes a fix verifiable.

You can expect an acknowledgement within a week. If you have not heard back
after that, assume the message went astray and send it again.

Please give us time to publish a fix before disclosing publicly. If you intend
to disclose on a schedule, say so in the first message and we will work to it.

## Supported versions

| Version | Supported |
| ------- | --------- |
| 1.x     | ✅        |
| < 1.0   | ❌        |

Fixes land on `main` and are released from there. Maintenance branches are cut
per minor version, so a fix can be backported to the latest `1.x` on request.

## What halfORM defends, and what it cannot

halfORM binds *values* as query parameters, always. SQL has no parameter for
an *identifier*, so column, relation and function names are interpolated into
the statement text, and halfORM checks them against the schema it introspected
rather than trusting them. Where that check is possible it is the boundary;
where a name cannot be checked — a function name passed to
`execute_function`, for instance — the application must not build it from
untrusted input.

Two areas are trusted by design, and it is worth being explicit about them:

- **The database you connect to.** Schema and relation names drive class
  generation, and a connection file decides which database and which role the
  process uses. A database you do not control is not untrusted input that
  halfORM sanitises; it is part of the trusted computing base.
- **Installed extensions.** The `half_orm` CLI imports them, which runs them.
  Unofficial extensions are approved per project and pinned to a digest of
  their code, but an extension you approve runs with your privileges.

Reports about either are still welcome — the boundaries above are where we
think the line is, not a list of things we refuse to look at.

## Scope

This policy covers the `half_orm` package and the `half_orm` CLI. Extensions
maintained by the halfORM organisation (`half-orm-dev`, `half-orm-inspect`,
`half-orm-gen`) have their own repositories; a report about one of them is
best filed there, but sending it here is fine and we will route it.
