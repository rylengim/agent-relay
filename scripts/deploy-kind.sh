#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --context kind-agent-relay [--image agent-relay:TAG]" >&2
  exit 2
}

context=""
image="agent-relay:local"
while (($#)); do
  case "$1" in
    --context) (($# >= 2)) || usage; context="$2"; shift 2 ;;
    --image) (($# >= 2)) || usage; image="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[[ "$context" == "kind-agent-relay" ]] || usage
[[ "$image" =~ ^agent-relay:[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}$ ]] || usage

for command in docker kind kubectl python3; do
  command -v "$command" >/dev/null || { echo "Required tool missing: $command" >&2; exit 1; }
done

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(dirname -- "$script_dir")"
kube=(kubectl --context "$context")

# Never create a cluster or silently fall back to the current kubeconfig context.
[[ "$(kubectl config get-contexts "$context" -o name)" == "$context" ]] || {
  echo "Create the local cluster first: kind create cluster --name agent-relay" >&2
  exit 1
}
"${kube[@]}" cluster-info >/dev/null
docker image inspect "$image" >/dev/null
kind load docker-image "$image" --name agent-relay

umask 077
deploy_tmp="$(mktemp -d)"
trap 'rm -rf -- "$deploy_tmp"' EXIT

# Render the requested image before applying: do not deploy :local as an
# intermediate step when replacing an already-running unique version.
sed "s|image: agent-relay:local|image: $image|" \
  "$project_dir/k8s/app.yaml" > "$deploy_tmp/app.yaml"

"${kube[@]}" apply -f "$project_dir/k8s/namespace.yaml"
secret_name="$("${kube[@]}" -n agent-relay get secret postgres-credentials --ignore-not-found -o name)"
if [[ -z "$secret_name" ]]; then
  # Files keep credentials out of command arguments and the repository.
  # A provided POSTGRES_PASSWORD is URL-escaped for SQLAlchemy; otherwise
  # generate a password once and preserve the resulting Secret on later runs.
  python3 - "$deploy_tmp" <<'PY'
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import quote

directory = Path(sys.argv[1])
password = os.environ.get("POSTGRES_PASSWORD") or secrets.token_hex(32)
(directory / "POSTGRES_PASSWORD").write_text(password)
(directory / "RELAY_DATABASE_URL").write_text(
    f"postgresql+psycopg://relay:{quote(password, safe='')}@postgres:5432/relay"
)
PY
  "${kube[@]}" -n agent-relay create secret generic postgres-credentials \
    --from-file="POSTGRES_PASSWORD=$deploy_tmp/POSTGRES_PASSWORD" \
    --from-file="RELAY_DATABASE_URL=$deploy_tmp/RELAY_DATABASE_URL"
fi

"${kube[@]}" apply -f "$project_dir/k8s/postgres.yaml"
"${kube[@]}" -n agent-relay rollout status deployment/postgres --timeout=180s
"${kube[@]}" apply -f "$project_dir/k8s/service.yaml" -f "$deploy_tmp/app.yaml"
"${kube[@]}" -n agent-relay rollout status deployment/agent-relay --timeout=180s
"${kube[@]}" -n agent-relay get pods,services,pvc
echo "Dashboard: kubectl --context $context -n agent-relay port-forward service/agent-relay 8000:8000"
