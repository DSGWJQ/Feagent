#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
E2E_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi

API_BASE_URL="${PLAYWRIGHT_API_URL:-http://localhost:8000}"
WEB_BASE_URL="${PLAYWRIGHT_BASE_URL:-http://localhost:5173}"
ITERATIONS="${ITERATIONS:-10}"
MIN_PASS_RATE="${MIN_PASS_RATE:-0.95}"

ARTIFACTS_ROOT="${E2E_DIR}/.m4-artifacts"
RUN_ID="$("${PYTHON_BIN}" -c "import datetime; print(datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'))")"
RUN_DIR="${ARTIFACTS_ROOT}/${RUN_ID}"

mkdir -p "${RUN_DIR}"

echo "[M4] run_id=${RUN_ID}"
echo "[M4] api=${API_BASE_URL}"
echo "[M4] web=${WEB_BASE_URL}"
echo "[M4] artifacts=${RUN_DIR}"

function http_get_status() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -sS -o /dev/null -w "%{http_code}" "${url}" || echo "000"
  else
    "${PYTHON_BIN}" - "${url}" <<'PY' 2>/dev/null || echo "000"
import sys, urllib.request
url = sys.argv[1]
try:
  with urllib.request.urlopen(url, timeout=3) as resp:
    print(resp.status)
except Exception:
  print("000")
PY
  fi
}

function wait_for_health() {
  local url="${API_BASE_URL}/health"
  local attempts=30
  local sleep_s=1

  echo "[M4] waiting for backend health: ${url}"
  for ((i=1; i<=attempts; i++)); do
    local code
    code="$(http_get_status "${url}")"
    if [[ "${code}" == "200" ]]; then
      echo "[M4] backend healthy (HTTP 200)"
      return 0
    fi
    echo "[M4] health not ready (HTTP ${code}) attempt ${i}/${attempts}"
    sleep "${sleep_s}"
  done

  echo "[M4] backend health check failed"
  return 1
}

function json_set() {
  local file="$1"
  local python_expr="$2"
  "${PYTHON_BIN}" - "$file" "$python_expr" <<'PY'
import json, os, sys
path = sys.argv[1]
expr = sys.argv[2]
data = {}
if os.path.exists(path):
  with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
ns = {"data": data}
exec(expr, ns, ns)  # noqa: S102 - controlled by script
with open(path, "w", encoding="utf-8") as f:
  json.dump(ns["data"], f, ensure_ascii=False, indent=2)
PY
}

function json_append_array() {
  local file="$1"
  local key="$2"
  local json_obj="$3"
  "${PYTHON_BIN}" - "$file" "$key" "$json_obj" <<'PY'
import json, os, sys
path = sys.argv[1]
key = sys.argv[2]
obj = json.loads(sys.argv[3])
data = {}
if os.path.exists(path):
  with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
arr = data.get(key)
if not isinstance(arr, list):
  arr = []
arr.append(obj)
data[key] = arr
with open(path, "w", encoding="utf-8") as f:
  json.dump(data, f, ensure_ascii=False, indent=2)
PY
}

wait_for_health

META_JSON="${RUN_DIR}/meta.json"
json_set "${META_JSON}" "data.update({'run_id': '${RUN_ID}', 'api_base_url': '${API_BASE_URL}', 'web_base_url': '${WEB_BASE_URL}', 'iterations': int('${ITERATIONS}'), 'min_pass_rate': float('${MIN_PASS_RATE}')})"

echo "[M4] verifying Seed API fixtures..."
SEED_JSON="${RUN_DIR}/seed-results.json"
json_set "${SEED_JSON}" "data.update({'passed': True, 'api_base_url': '${API_BASE_URL}', 'fixtures': [], 'checks': []})"

if command -v curl >/dev/null 2>&1; then
  # Test-mode header required (negative test)
  code="$(curl -sS -o /dev/null -w "%{http_code}" "${API_BASE_URL}/api/test/workflows/fixture-types" || echo "000")"
  json_append_array "${SEED_JSON}" "checks" "{\"name\":\"fixture-types_requires_test_mode\",\"http_status\":${code}}"

  # Invalid fixture type should be rejected
  invalid_body_file="${RUN_DIR}/seed-invalid-fixture.json"
  cat >"${invalid_body_file}" <<JSON
{
  "fixture_type": "__m4_invalid_fixture__",
  "project_id": "m4_seed_verify"
}
JSON

  invalid_code="$(curl -sS -o "${RUN_DIR}/seed-invalid-fixture-resp.json" -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -H "X-Test-Mode: true" \
    -X POST "${API_BASE_URL}/api/test/workflows/seed" \
    --data @"${invalid_body_file}" || echo "000")"
  json_append_array "${SEED_JSON}" "checks" "{\"name\":\"seed_rejects_invalid_fixture_type\",\"http_status\":${invalid_code}}"

  # Fixture types list
  curl -sS "${API_BASE_URL}/api/test/workflows/fixture-types" \
    -H "X-Test-Mode: true" \
    -o "${RUN_DIR}/fixture-types.json"

  "${PYTHON_BIN}" - "${RUN_DIR}/fixture-types.json" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
  data = json.load(f)
types = set(data.get("fixture_types") or [])
required = {"main_subgraph_only", "with_isolated_nodes", "side_effect_workflow", "invalid_config"}
missing = sorted(required - types)
if missing:
  raise SystemExit(f"Missing fixture types: {missing}")
PY

  fixture_types=("main_subgraph_only" "with_isolated_nodes" "side_effect_workflow" "invalid_config")
  for fixture_type in "${fixture_types[@]}"; do
    body_file="${RUN_DIR}/seed-${fixture_type}.json"
    resp_file="${RUN_DIR}/seed-${fixture_type}-resp.json"
    cleanup_resp_file="${RUN_DIR}/cleanup-${fixture_type}-resp.json"

    cat >"${body_file}" <<JSON
{
  "fixture_type": "${fixture_type}",
  "project_id": "m4_seed_verify",
  "custom_metadata": {
    "m4_run_id": "${RUN_ID}",
    "m4_fixture": "${fixture_type}"
  }
}
JSON

    http_code="$(curl -sS -o "${resp_file}" -w "%{http_code}" \
      -H "Content-Type: application/json" \
      -H "X-Test-Mode: true" \
      -X POST "${API_BASE_URL}/api/test/workflows/seed" \
      --data @"${body_file}" || echo "000")"

    workflow_id="$("${PYTHON_BIN}" - "${resp_file}" <<'PY' || true
import json, sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
  data = json.load(f)
print(data.get("workflow_id") or "")
PY
)"

    cleanup_token="$("${PYTHON_BIN}" - "${resp_file}" <<'PY' || true
import json, sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
  data = json.load(f)
print(data.get("cleanup_token") or "")
PY
)"

    get_before_code="$(curl -sS -o /dev/null -w "%{http_code}" "${API_BASE_URL}/api/workflows/${workflow_id}" || echo "000")"

    cleanup_body_file="${RUN_DIR}/cleanup-${fixture_type}.json"
    cat >"${cleanup_body_file}" <<JSON
{
  "cleanup_tokens": ["${cleanup_token}"],
  "delete_by_source": false
}
JSON

    cleanup_code="$(curl -sS -o "${cleanup_resp_file}" -w "%{http_code}" \
      -H "Content-Type: application/json" \
      -H "X-Test-Mode: true" \
      -X DELETE "${API_BASE_URL}/api/test/workflows/cleanup" \
      --data @"${cleanup_body_file}" || echo "000")"

    get_after_code="$(curl -sS -o /dev/null -w "%{http_code}" "${API_BASE_URL}/api/workflows/${workflow_id}" || echo "000")"

    fixture_ok=true
    if [[ "${http_code}" != "201" ]]; then fixture_ok=false; fi
    if [[ "${get_before_code}" != "200" ]]; then fixture_ok=false; fi
    if [[ "${cleanup_code}" != "200" ]]; then fixture_ok=false; fi
    if [[ "${get_after_code}" != "404" ]]; then fixture_ok=false; fi

    if [[ "${fixture_ok}" != "true" ]]; then
      json_set "${SEED_JSON}" "data['passed'] = False"
    fi

    json_append_array "${SEED_JSON}" "fixtures" "$("${PYTHON_BIN}" - <<PY
import json
print(json.dumps({
  "fixture_type": "${fixture_type}",
  "seed_http_status": int("${http_code}"),
  "workflow_id": "${workflow_id}",
  "cleanup_token": "${cleanup_token}",
  "get_before_http_status": int("${get_before_code}"),
  "cleanup_http_status": int("${cleanup_code}"),
  "get_after_http_status": int("${get_after_code}"),
  "passed": ${fixture_ok},
}, ensure_ascii=False))
PY
)"
  done
else
  echo "[M4] curl not found; skipping Seed API verification (requires curl)"
  json_set "${SEED_JSON}" "data.update({'passed': False, 'skipped': True, 'reason': 'curl_not_found'})"
fi

echo "[M4] running deterministic Playwright tests ${ITERATIONS} time(s)..."
cd "${WEB_DIR}"

for ((i=1; i<=ITERATIONS; i++)); do
  run_json="${RUN_DIR}/playwright-run-${i}.json"
  run_log="${RUN_DIR}/playwright-run-${i}.log"

  echo "[M4] iteration ${i}/${ITERATIONS}"

  set +e
  CI=1 \
  E2E_TEST_MODE=deterministic \
  PLAYWRIGHT_API_URL="${API_BASE_URL}" \
  PLAYWRIGHT_BASE_URL="${WEB_BASE_URL}" \
  npx playwright test --project=deterministic --reporter=json 1>"${run_json}" 2>"${run_log}"
  exit_code="$?"
  set -e

  echo "${exit_code}" > "${RUN_DIR}/playwright-run-${i}.exitcode"
done

echo "[M4] summarizing results..."
set +e
"${PYTHON_BIN}" "${SCRIPT_DIR}/collect-metrics.py" summarize \
  --run-dir "${RUN_DIR}" \
  --min-pass-rate "${MIN_PASS_RATE}" \
  --out-summary "${RUN_DIR}/summary.json" \
  --out-report "${RUN_DIR}/report.md" \
  --schema "${SCRIPT_DIR}/metrics.schema.json" \
  --metrics-file "${ARTIFACTS_ROOT}/metrics.json"
summary_exit="$?"
set -e

echo "[M4] report: ${RUN_DIR}/report.md"
exit "${summary_exit}"
