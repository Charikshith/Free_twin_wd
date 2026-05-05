#!/bin/bash
# ============================================================================
# Start the full OTel multi-agent calculator stack (v2)
#
# Usage:  bash start.sh
# Stop:   Ctrl+C (kills all background processes)
#
# Launches:
#   - kubectl port-forwards for Alloy / Loki / Grafana / Prometheus
#   - otel_agent_v2/mcp_server.py add_sub   -> :8081 (prom :8001)
#   - otel_agent_v2/mcp_server.py mul_div   -> :8082 (prom :8002)
#   - uvicorn otel_agent_v2.api:app         -> :8080 (prom :8000)
#   - otel_agent_v2/kpi_proxy.py            -> :8900
# ============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$REPO_ROOT/otel_agent_v2/.env"
NAMESPACE="${NAMESPACE:-monitoring}"

# Track background PIDs so we can clean up on exit
PIDS=()

cleanup() {
    echo ""
    echo "[shutdown] Stopping all processes..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null
    echo "[shutdown] Done."
}
trap cleanup EXIT INT TERM

# ── 0. Pre-flight: require otel_agent_v2/.env with API_KEY ──────────────────
echo "=== Pre-flight checks ==="

if [ ! -f "$ENV_FILE" ]; then
    echo "  [FAIL] .env not found at: $ENV_FILE"
    echo ""
    echo "  Create it with at least:"
    echo "      API_KEY=<your-groq-or-bedrock-key>"
    echo "      # optional:"
    echo "      # LLM_BASE_URL=https://api.groq.com/openai/v1/"
    echo "      # LLM_MODEL=llama-3.3-70b-versatile"
    exit 1
fi
echo "  [OK] $ENV_FILE"

# Export variables from the v2 .env so every child process inherits them
# (python-dotenv in api.py/cli.py also loads it from CWD, but exporting here
# means the uvicorn/mcp children see API_KEY even before load_dotenv runs).
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

if [ -z "${API_KEY:-}" ]; then
    echo "  [FAIL] API_KEY is not set in $ENV_FILE"
    exit 1
fi
echo "  [OK] API_KEY loaded from .env"

# ── 1. Kubernetes namespace pre-flight ──────────────────────────────────────
echo ""
echo "=== Kubernetes checks ==="

if ! kubectl get namespace "$NAMESPACE" > /dev/null 2>&1; then
    echo "  [FAIL] Kubernetes namespace '$NAMESPACE' does not exist."
    echo ""
    echo "  Either:"
    echo "    1. Create it: kubectl create namespace $NAMESPACE"
    echo "    2. Re-run with the correct namespace:"
    echo "       NAMESPACE=<your-namespace> bash start.sh"
    echo ""
    echo "  If you deployed the Grafana stack into a different namespace,"
    echo "  update your port-forwards and datasource hostnames to match."
    exit 1
fi
echo "  [OK] Namespace '$NAMESPACE' exists"

# ── 2. Port-forwards ────────────────────────────────────────────────────────
echo ""
echo "=== Starting port-forwards ==="

kubectl port-forward -n "$NAMESPACE" svc/alloy 4317:4317 &
PIDS+=($!)
echo "[port-forward] Alloy  (OTLP gRPC)  -> localhost:4317"

kubectl port-forward -n "$NAMESPACE" svc/loki 3100:3100 &
PIDS+=($!)
echo "[port-forward] Loki   (logs)        -> localhost:3100"

kubectl port-forward -n "$NAMESPACE" svc/grafana 3000:80 &
PIDS+=($!)
echo "[port-forward] Grafana (UI)         -> localhost:3000"

kubectl port-forward -n "$NAMESPACE" svc/kube-prom-stack-kube-prome-prometheus 9090:9090 &
PIDS+=($!)
echo "[port-forward] Prometheus           -> localhost:9090"

kubectl port-forward -n "$NAMESPACE" svc/tempo 3200:3200 &
PIDS+=($!)
echo "[port-forward] Tempo  (traces HTTP) -> localhost:3200"

# Wait for port-forwards to establish
sleep 3

# ── 3. Verify connectivity ──────────────────────────────────────────────────
echo ""
echo "=== Verifying services ==="
FAIL=0

for check in "localhost:3000/api/health Grafana" "localhost:3100/ready Loki" "localhost:9090/-/ready Prometheus" "localhost:3200/ready Tempo"; do
    URL=$(echo "$check" | cut -d' ' -f1)
    NAME=$(echo "$check" | cut -d' ' -f2)
    if curl -s --max-time 3 "http://$URL" > /dev/null 2>&1; then
        echo "  [OK]   $NAME"
    else
        echo "  [FAIL] $NAME — not reachable at $URL"
        FAIL=1
    fi
done

if [ "$FAIL" -eq 1 ]; then
    echo ""
    echo "WARNING: Some services are not reachable. Check kubectl get pods -n $NAMESPACE"
    echo "Continuing anyway..."
fi

# ── 4. MCP tool servers (v2) ────────────────────────────────────────────────
# NOTE: v2 modules import as `otel_agent_v2.<name>`, so every process must be
# launched from the repo root — NOT from inside otel_agent_v2/.
echo ""
echo "=== Starting MCP tool servers (v2) ==="

cd "$REPO_ROOT"

python otel_agent_v2/mcp_server.py add_sub &
PIDS+=($!)
echo "[mcp] add_sub server -> localhost:8081 (metrics :8001)"

python otel_agent_v2/mcp_server.py mul_div &
PIDS+=($!)
echo "[mcp] mul_div server -> localhost:8082 (metrics :8002)"

# Wait for MCP servers to be ready
echo ""
echo "Waiting for MCP servers to start..."
for PORT in 8081 8082; do
    for i in $(seq 1 30); do
        if curl -s --max-time 1 "http://localhost:$PORT/mcp" > /dev/null 2>&1; then
            echo "  [OK] localhost:$PORT is ready"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "  [WARN] localhost:$PORT not ready after 30s — starting agent API anyway"
        fi
        sleep 1
    done
done

# ── 4. Agent API (v2, uvicorn) ──────────────────────────────────────────────
echo ""
echo "=== Starting Agent API (v2) ==="

uvicorn otel_agent_v2.api:app --host 0.0.0.0 --port 8080 &
PIDS+=($!)
echo "[agent] otel_agent_v2.api:app -> localhost:8080 (metrics :8000)"

# ── 5. KPI proxy ────────────────────────────────────────────────────────────
echo ""
echo "=== Starting KPI proxy ==="

python otel_agent_v2/kpi_proxy.py &
PIDS+=($!)
echo "[kpi]   kpi_proxy -> localhost:8900"

# ── 6. Ready ────────────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  All services started!"
echo ""
echo "  Agent API:    http://localhost:8080/run"
echo "  Health:       http://localhost:8080/health"
echo "  KPI proxy:    http://localhost:8900/kpi/all"
echo "  Grafana:      http://localhost:3000"
echo "  Prometheus:   http://localhost:9090/targets"
echo ""
echo "  Press Ctrl+C to stop everything"
echo "============================================"

# Keep script alive until Ctrl+C
wait
