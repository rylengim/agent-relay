#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -e .env ]]; then
  umask 077
  python3 - <<'PY'
import secrets
from pathlib import Path
Path('.env').write_text('POSTGRES_PASSWORD=' + secrets.token_hex(24) + '\n')
PY
  echo 'Created .env with a random local database password.'
fi
