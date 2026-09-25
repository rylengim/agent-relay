# AI usage report

## Scope and sources

Codex assisted with the user's request to complete Homework 3 and publish the
resulting repository. The user explicitly authorized project changes, GitHub
publication, and homework submission. Work starts from
[alexeygrigorev/agent-relay](https://github.com/alexeygrigorev/agent-relay); the
starter application is not claimed as newly written work.

The agent read the
[official homework](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/cohorts/2026/homework/03-deployment/homework.md),
submission page, starter `SPEC.md`, and existing code/tests. Official Kubernetes
and kind documentation informed image loading, probes, and manifest replacement.
Relevant skills included CI/CD automation, Git workflow, and documentation.

## Work performed with AI assistance

- Identified the required starter and six submission questions.
- Adapted persistence for PostgreSQL while retaining SQLite. Transactions and
  row locks coordinate claims, leases, completion, recovery, and idempotency.
- Added storage transaction coverage and a separate integration suite against a
  running API. The HTTP suite leaves records available for dashboard inspection
  and does not import the app or reset its database.
- Added a non-root Docker image, PostgreSQL 17 Compose stack, generated local
  credentials, and persistent database storage.
- Added Kubernetes workloads, internal Services, storage, health probes, resource
  limits, and a rollout script requiring an explicit local context.
- Added a workflow that tests before building a unique image and deploying during
  a locally requested `act` run.
- Wrote reproduction commands, operational notes, and prepared homework answers.

## Collaboration and decisions

The main agent assigned bounded work to subagents: official requirements,
database behavior/testing, HTTP integration, and Kubernetes manifests. The main
agent retained integration, environment execution, dashboard checks, publication,
and submission. Shared files were divided by ownership.

The existing HTTP protocol and token model were preserved. PostgreSQL row locks
coordinate API processes; SQLite retains its writer reservation. Destructive
starter tests and the running HTTP integration use separate databases. A single
Kubernetes app replica keeps the exercise small; rolling updates retain the old
ready replica while the next version starts.

The rollout script generates credentials only when the Secret is missing,
preserves them on later runs, loads the requested image into kind, and renders
that image before applying the app manifest. Act's host runner retains the same
user's Docker and kubeconfig access. GitHub-hosted runs test and build only.

Environment setup encountered a VPN routing conflict, resolved using explicit
Docker networks: `172.28.0.0/16` for kind and `172.29.0.0/24` for Compose. The README
explains how to adjust these local choices.

## Verification and evidence

Generated changes were treated as work to verify. The Kubernetes contribution
was checked with Bash syntax validation, YAML parsing, kubectl's local image
substitution, and rejection of missing or unsafe context/image arguments. These
checks do not establish successful runtime deployment.

The main agent then observed 15 starter/storage tests passing on SQLite and
PostgreSQL, plus the real HTTP acceptance test passing against local, Docker,
Compose, and kind instances. PostgreSQL persistence was checked across a Compose
restart. The Kubernetes pods became ready with a bound 1 GiB PVC. Two local
`act` runs deployed v1 and v2 with distinct image tags, and the browser showed
the v2 heading and a persisted completed task without console errors.

A temporary failing test was introduced to verify the deployment gate. The
workflow stopped with one failed and 15 passed tests before image build or
deployment; the running image stayed unchanged. The temporary failure was
removed after the check. [Execution details](verification.md) and
[submission status](homework-answers.md) are recorded separately. The course
submission was still pending when this report was updated.

Database passwords, bearer/claim tokens, kubeconfig contents, and temporary
dashboard credentials are excluded from published evidence and source control.
