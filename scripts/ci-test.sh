#!/usr/bin/env bash
# Disposable PostgreSQL and separate databases for destructive and HTTP tests.
set -euo pipefail
cd "$(dirname "$0")/.."
ci_tmp="$(mktemp -d)"
pg_name="relay-ci-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:12])')"
api_pid=""
cleanup() {
  if [[ -n "$api_pid" ]]; then kill "$api_pid" 2>/dev/null || true; wait "$api_pid" 2>/dev/null || true; fi
  docker rm -f "$pg_name" >/dev/null 2>&1 || true
  rm -rf "$ci_tmp"
}
trap cleanup EXIT
umask 077
python3 - <<'PY' > "$ci_tmp/postgres.env"
import secrets
print('POSTGRES_PASSWORD=' + secrets.token_hex(24))
print('POSTGRES_USER=relay')
print('POSTGRES_DB=relay_tests')
PY
docker run -d --name "$pg_name" --env-file "$ci_tmp/postgres.env" \
  -p 127.0.0.1::5432 postgres:17 >/dev/null
for attempt in {1..60}; do
  if docker exec "$pg_name" pg_isready -h 127.0.0.1 -U relay -d relay_tests >/dev/null 2>&1; then break; fi
  if [[ "$attempt" == 60 ]]; then echo 'CI PostgreSQL did not become ready.' >&2; exit 1; fi
  sleep 1
done
pg_port="$(docker port "$pg_name" 5432/tcp | cut -d: -f2)"
pg_password="$(sed -n 's/^POSTGRES_PASSWORD=//p' "$ci_tmp/postgres.env")"
export RELAY_DATABASE_URL="postgresql+psycopg://relay:$pg_password@127.0.0.1:$pg_port/relay_tests"
uv sync --locked
uv run --locked pytest -q test_agent_relay.py test_storage_transactions.py

# The running API gets its own database: starter fixtures never touch it.
docker exec "$pg_name" createdb -U relay relay_http
export RELAY_DATABASE_URL="postgresql+psycopg://relay:$pg_password@127.0.0.1:$pg_port/relay_http"
api_port="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
uv run --locked uvicorn main:app --host 127.0.0.1 --port "$api_port" > "$ci_tmp/api.log" 2>&1 &
api_pid=$!
export RELAY_TEST_BASE_URL="http://127.0.0.1:$api_port"
for attempt in {1..60}; do
  if curl --connect-timeout 2 --max-time 3 -fsS "$RELAY_TEST_BASE_URL/ready" >/dev/null 2>&1; then break; fi
  if ! kill -0 "$api_pid" 2>/dev/null || [[ "$attempt" == 60 ]]; then
    echo 'CI API did not become ready.' >&2; cat "$ci_tmp/api.log"; exit 1
  fi
  sleep 1
done
uv run --locked pytest -c integration/pytest.ini integration/ -q
echo 'Starter, storage, and real HTTP PostgreSQL tests passed.'
