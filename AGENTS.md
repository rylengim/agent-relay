# Homework 3 contributor guide

- Preserve the HTTP protocol and credential rules in SPEC.md.
- SQLite and PostgreSQL must keep claim, heartbeat, recovery, and terminal
  transitions atomic. Test concurrency and idempotency after storage changes.
- Starter tests recreate tables: only run them against a dedicated test DB.
- Run real HTTP integration tests separately with RELAY_TEST_BASE_URL.
- Never commit databases, credentials, .env, kubeconfig, or unredacted logs.
- Docker and Kubernetes targets are local homework environments. Explicitly use
  kind-agent-relay; do not deploy to another current Kubernetes context.
- Tests must pass before building and deploying a version. Use unique image tags
  and wait for rollout completion. Do not suppress failures or skip tests.
- Keep README and docs/homework-answers.md aligned with verified results.
