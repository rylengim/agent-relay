# Agent Relay — Homework 3

An HTTP task relay built with FastAPI and SQLAlchemy. Agents register, send tasks,
claim work, and return results. The relay persists identities, tasks, and delivery
attempts; workers execute the work. The browser dashboard displays the lifecycle
through the authenticated API.

This [fork](https://github.com/rylengim/agent-relay) extends the
[Agent Relay starter](https://github.com/alexeygrigorev/agent-relay) for
[AI Dev Tools Zoomcamp Homework 3](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/cohorts/2026/homework/03-deployment/homework.md)
with PostgreSQL, real HTTP integration testing, Docker, Compose, Kubernetes, and
CI/CD. Everything runs locally; no cloud account, LLM API key, or message broker
is required.

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/).
- Docker Engine with Compose, accessible by your current user.
- For Kubernetes: [kind](https://kind.sigs.k8s.io/docs/user/quick-start/) and
  [kubectl](https://kubernetes.io/docs/tasks/tools/).
- For local CI/CD: [act](https://nektosact.com/) and GNU `timeout`.

The homework environment installed kind 0.33.0, kubectl 1.37.1, act 0.2.89,
and local uv 0.11.24. The image and hosted CI pin uv 0.12.19; the containers
use Python 3.13 and PostgreSQL 17.

Run the remaining commands from the repository root:

```bash
git clone https://github.com/rylengim/agent-relay.git
cd agent-relay
uv sync --locked
```

## Run with local SQLite

```bash
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8000
```

Open [the local dashboard](http://127.0.0.1:8000/). The default database is
`./agent-relay.db`; `RELAY_DATABASE_URL` selects another SQLite file or PostgreSQL.
`/health` checks the process; `/ready` checks database connectivity and the schema.

Register identities through `POST /api/v1/agents` and keep their tokens privately.
The integration command below can create demonstration identities and save
private credentials. Paste the sender's token into the dashboard to inspect sent tasks. The deterministic worker uppercases input
and saves its registration credentials in a private local file:

```bash
uv run --locked python main.py worker --base-url http://127.0.0.1:8000 --name uppercase --credentials ./uppercase-credentials.json --worker-id laptop-1
```

The worker heartbeats during long tasks. Leases default to 60 seconds; expired
leases can be claimed again. [SPEC.md](SPEC.md) defines the protocol, authentication,
idempotency, retry behavior, and acceptance scenarios.

## Tests: keep destructive fixtures separate

Starter/storage tests **drop and recreate tables**. Run them separately against
their default scratch SQLite database, never a running app's database:

```bash
env -u RELAY_DATABASE_URL -u DATABASE_URL uv run --locked pytest -q test_agent_relay.py test_storage_transactions.py
```

The integration suite uses a running HTTP server and its real database. It creates
fresh identities without resetting tables, exercises the task flow, and checks
authentication, isolation, exclusive claims, heartbeat, and idempotency:

```bash
RELAY_TEST_BASE_URL=http://127.0.0.1:8000 uv run --locked pytest -c integration/pytest.ini integration/ -q
```

Use that explicit path/configuration to avoid the starter's destructive fixtures.
Add `-s --save-demo-credentials` to save private temporary credentials for inspecting
the completed task in the dashboard, then remove that temporary file. See
[integration/README.md](integration/README.md).

## Docker container

```bash
docker build -t agent-relay:local .
docker run -d --name relay-docker -p 127.0.0.1:8102:8000 -v relay-sqlite-data:/data agent-relay:local
RELAY_TEST_BASE_URL=http://127.0.0.1:8102 uv run --locked pytest -c integration/pytest.ini integration/ -q
```

Open [the container dashboard](http://127.0.0.1:8102/) once the container is healthy.
The image runs as a non-root user and binds Uvicorn to `0.0.0.0:8000` inside the
container. Docker's `-p` publishes the port. The named volume preserves SQLite
when the container is recreated.

## Compose with PostgreSQL

```bash
bash scripts/setup-local.sh
docker compose up --build -d --wait
RELAY_TEST_BASE_URL=http://127.0.0.1:8100 uv run --locked pytest -c integration/pytest.ini integration/ -q
docker compose exec postgres psql -U relay -d relay -c 'SELECT status, count(*) FROM tasks GROUP BY status;'
```

Open [the Compose dashboard](http://127.0.0.1:8100/). Setup creates an ignored `.env`
with a random password. The API connects to service hostname `postgres`, port 5432,
database `relay`, user `relay`. PostgreSQL uses the `postgres-data` named volume.
`docker compose down` retains it; adding `--volumes` removes its data.

The Compose network defaults to `172.29.0.0/24`, chosen to avoid a VPN route
conflict in the homework environment. Set `RELAY_COMPOSE_SUBNET` in `.env` to
another unused subnet if your routes overlap.

## Local Kubernetes

Create the cluster once. A VPN route conflict in the homework environment was
resolved by explicitly creating the Docker `kind` network before cluster creation.
If that network already exists, keep it and omit the first command. Choose an
unused subnet if these addresses overlap your routes.

```bash
docker network create --subnet 172.28.0.0/16 kind
kind create cluster --name agent-relay --wait 180s
docker build -t agent-relay:local .
bash scripts/deploy-kind.sh --context kind-agent-relay --image agent-relay:local
kubectl --context kind-agent-relay -n agent-relay port-forward service/agent-relay 8104:8000
```

In another terminal:

```bash
RELAY_TEST_BASE_URL=http://127.0.0.1:8104 uv run --locked pytest -c integration/pytest.ini integration/ -q
kubectl --context kind-agent-relay -n agent-relay get pods,services,pvc
```

Open [the Kubernetes dashboard](http://127.0.0.1:8104/). The deployment script
requires the existing, explicitly supplied `kind-agent-relay` context. It loads
the chosen image, creates the namespace and database Secret if absent, waits for
PostgreSQL, applies the requested app image, and waits for rollout. Existing
credentials are preserved; generated credentials never enter source control.

The manifests use namespace `agent-relay`, one app replica, PostgreSQL with a
`Recreate` strategy, internal Services, resource limits, and health probes. A 1 GiB
PVC preserves database files across pod replacement. Storage inside the local
kind node does not survive deleting the whole cluster.

## CI/CD

Run only the PostgreSQL verification stage:

```bash
bash scripts/ci-test.sh
```

It creates a disposable PostgreSQL container, runs starter/storage tests against
`relay_tests`, then starts a real API against a separate `relay_http` database and
runs the integration suite. Cleanup removes only these temporary CI resources.

Run the full workflow against the existing local cluster:

```bash
timeout 900 act workflow_dispatch
```

[.actrc](.actrc) selects `.github/workflows/ci.yml` and maps `ubuntu-latest` to
`-self-hosted`, act's host runner. Run as the same user who can access Docker and
the `kind-agent-relay` kubeconfig context, with the local tools on `PATH`. This
executes checked-out workflow code directly on your machine.

The workflow tests first, then builds a unique tag from the commit, time, and a
random suffix. Only a local `act workflow_dispatch` run deploys to kind.
GitHub-hosted push/PR/manual runs test and build; they cannot access this local
cluster and do not deploy. Failed tests prevent later image build and deployment,
leaving the existing version running.

For the homework v2 exercise, change the dashboard heading to `Agent Relay v2`,
run the workflow again, and verify the heading and integration flow through the
forwarded Kubernetes service. The script renders the selected image before apply,
avoiding an intermediate deployment of `agent-relay:local`.

## Rollback and persistence

Inspect and restore a previous app revision without replacing the database:

```bash
kubectl --context kind-agent-relay -n agent-relay rollout history deployment/agent-relay
kubectl --context kind-agent-relay -n agent-relay rollout undo deployment/agent-relay
kubectl --context kind-agent-relay -n agent-relay rollout status deployment/agent-relay --timeout=180s
```

Alternatively, pass a previously built image tag to `scripts/deploy-kind.sh`.
Stop Compose with `docker compose down`, the standalone container with
`docker stop relay-docker`, and port forwarding with Ctrl-C. Keep volumes and the
kind cluster to retain demonstration data.

## Project map

| Path | Responsibility |
| --- | --- |
| `main.py`, `schemas.py`, `dashboard.html`, `worker.py` | API, request validation, dashboard, deterministic worker |
| `database.py`, `storage.py` | Models and transactional task/lease operations |
| `test_agent_relay.py`, `test_storage_transactions.py` | Starter protocol and database concurrency tests |
| `integration/` | Real HTTP acceptance flow against a running app |
| `Dockerfile`, `compose.yaml` | Image and PostgreSQL Compose stack |
| `k8s/`, `scripts/deploy-kind.sh` | Local Kubernetes workloads and rollout |
| `.github/workflows/ci.yml`, `scripts/ci-test.sh` | Test, build, local deployment workflow |

PostgreSQL uses task-row locks and `FOR UPDATE SKIP LOCKED` for claims; SQLite
retains `BEGIN IMMEDIATE`. Heartbeat, completion, and recovery coordinate through
the same task lock. Schema creation is serialized for concurrent API startup.
The protocol and token handling remain defined by the starter specification.

See the [verified execution record](docs/verification.md),
[homework answers and submission status](docs/homework-answers.md), and
[AI usage report](docs/ai-usage.md). The verified runs covered SQLite, Docker,
Compose, kind, v1/v2 workflow rollouts, and a deliberate failing-test deployment gate.
