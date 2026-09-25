# Homework 3 verification — 25 September 2026

The following checks were executed against this fork, with AI coding assistance.
This is a local deployment; no cloud account or runtime LLM was used.

## Protocol and storage

- Starter and added storage/concurrency tests: **15 passed on SQLite** and
  **15 passed on PostgreSQL 17**.
- PostgreSQL tests use a dedicated database, never the running demo database.
- Added regressions cover competing terminal submissions, recovery races,
  heartbeat/recovery coordination, sender-scoped idempotency, database URL
  normalization, and concurrent schema creation.
- A disposable mutation check removed row locks: the regression tests detected
  conflicting results being accepted and repeated expiry of a single lease.
- The starter's FastAPI/Starlette TestClient reports a dependency deprecation
  warning about httpx. No tests are skipped and the warning is not suppressed.

## Real HTTP acceptance scenario

The same integration test registers three fresh identities (sender, recipient,
and unauthorized observer), sends a task, claims it, heartbeats, submits its
result, and reads the result and delivery history as the sender. It also checks
idempotent retries and access boundaries.

| Environment | Endpoint used | Result |
| --- | --- | --- |
| Local SQLite API | `http://127.0.0.1:8103` | 1 passed |
| Docker `agent-relay:local`, published port | `http://127.0.0.1:8102` | 1 passed |
| Compose API + PostgreSQL | `http://127.0.0.1:8100` | 1 passed |
| kind via port forwarding | `http://127.0.0.1:8104` | 1 passed |
| kind after v2 deployment | `http://127.0.0.1:8104` | 1 passed |

The actual browser dashboard was inspected in all four environments. It showed
`completed`, output `HELLO FROM HOMEWORK 3`, and one completed delivery attempt.
The v2 browser inspection found no console errors or warnings.

Compose SQL inspection identified **PostgreSQL 17.11**, database `relay`, and a
completed task row. Restarting both the API and PostgreSQL preserved the task,
its result, and the credentials used by the dashboard.

## Kubernetes

Cluster `agent-relay`, context `kind-agent-relay`, namespace `agent-relay`:

- API and PostgreSQL pods reached **1/1 Ready**.
- PostgreSQL PVC `postgres-data` was **Bound**, capacity **1 GiB**.
- API readiness `/ready` queries the database; `/health` supplies liveness.
- Internal Services expose API port 8000 and PostgreSQL port 5432.
- Every deployment explicitly targets the local kind context.

## CI/CD

The GitHub Actions workflow was executed locally with the documented `act`
host runner. Both successful runs ran 15 starter/storage tests and the real
HTTP integration test against separate disposable PostgreSQL databases, built
a uniquely tagged image, loaded it into kind, and waited for rollout success.

| Run | Deployed image | Result |
| --- | --- | --- |
| v1 | `agent-relay:1c25e26-1790364540-8df41a5e` | Job succeeded |
| v2 | `agent-relay:8a453f3-1790364599-c4461b3d` | Job succeeded |

The second run followed the committed heading change. The deployed browser
title and h1 both read **Agent Relay v2**. The previously completed Kubernetes
task remained visible after the rollout.

A temporary deliberately failing test was added to the storage test file and
the same workflow was run again. It reported **1 failed, 15 passed**, exited
unsuccessfully, and ran neither the build nor deploy step. The deployed image
remained `agent-relay:8a453f3-1790364599-c4461b3d`. The temporary test was then
removed; it is not part of the submitted test suite.

## Issues found and resolved

- Docker socket access required the user to grant access to this session.
- VPN routes covered Docker's automatic address pools. Explicit local subnets
  let kind and Compose create their networks without changing the VPN.
- The system filesystem filled while pulling/building images. Regenerable
  Docker build cache was cleared; application data volumes were preserved.
- PostgreSQL readiness now checks TCP, avoiding its temporary socket-only
  initialization server.
- `kubectl set image --local` emitted no manifest for an unchanged tag; the
  deploy script now renders the validated image tag before applying it.
- `act` requires checkout to populate its host-runner workspace. Keeping that
  step fixed the initial missing-script error.

GitHub publication and course submission status are recorded in
[homework-answers.md](homework-answers.md).
