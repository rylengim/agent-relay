# Real HTTP acceptance test

This suite talks to a running API backed by its real database. It registers
three unique test agents, sends a task, claims and completes it, and reads back
the persisted result and delivery attempt. It also verifies authenticated access,
inbox isolation, exclusive claims, heartbeat, and idempotent submissions and results.
It uses no application imports, in-process TestClient, mocks, database resets, or
table cleanup. Test records remain available for dashboard inspection.

Start the API with its database first, then run from the project directory:

```bash
RELAY_TEST_BASE_URL=http://127.0.0.1:8000 \
  uv run pytest -c integration/pytest.ini integration/ -q
```

The explicit configuration selects only this integration suite. The starter's
`test_agent_relay.py` resets its database and must be run separately against a
disposable database. This suite fails clearly if the URL is absent, unreachable,
or the API/database is not ready. If enrollment is enabled on the server, provide
its secret through `RELAY_TEST_ENROLLMENT_SECRET`.

To also save the sender and recipient credentials for a local dashboard check:

```bash
RELAY_TEST_BASE_URL=http://127.0.0.1:8000 \
  uv run pytest -c integration/pytest.ini integration/ -q -s --save-demo-credentials
```

This prints only the temporary file path and task ID. The credentials file is
created with mode `0600` in the system temporary directory. Use the sender's
token to view the completed task in the dashboard, then remove that temporary
file when finished. Tokens are never printed by the test. Avoid pytest's
`--showlocals` option, which can display credentials if an assertion fails.
Set `RELAY_TEST_ARTIFACT_DIR` to another writable temporary directory when needed;
credential export rejects directories inside the repository, including an
automatic fallback there when system temporary directories are unavailable.
