# Grafana Observability Stack — Helm Setup Guide

Full LGTM stack (Loki + Grafana + Tempo + Prometheus) with Grafana Alloy as the
telemetry collector, deployed to a local Kubernetes cluster via Helm.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| kubectl | any | connected to your local cluster |
| helm | >= 3.10 | `helm version` to verify |
| Kubernetes | >= 1.25 | Docker Desktop / kind / minikube all work |

All commands below are run from this `Grafana_stackv1/` directory.

---

## Step 1 — Add Helm repositories

`kube-prometheus-stack` lives in the **prometheus-community** repo, not the Grafana repo.

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

---

## Step 2 — Create the monitoring namespace

```bash
kubectl create namespace monitoring
```

---

## Step 3 — Install the stack (order matters)

Install in this order so that each service can resolve its dependencies.

### 3a. Prometheus + Alertmanager (kube-prometheus-stack)

```bash
helm install kube-prom-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values prometheus-values.yaml
```

Wait for Prometheus to be ready before continuing:

```bash
kubectl rollout status -n monitoring statefulset/prometheus-kube-prom-stack-kube-prome-prometheus
```

### 3b. Loki

```bash
helm install loki grafana/loki \
  --namespace monitoring \
  --values loki-values.yaml
```

### 3c. Tempo

```bash
helm install tempo grafana/tempo \
  --namespace monitoring \
  --values tempo-values.yaml
```

### 3d. Grafana Alloy (telemetry collector / OTLP receiver)

```bash
helm install alloy grafana/alloy \
  --namespace monitoring \
  --values alloy-values.yaml
```

### 3e. Grafana

```bash
helm install grafana grafana/grafana \
  --namespace monitoring \
  --values grafana-values.yaml
```

---

## Step 4 — Verify all pods are running

```bash
kubectl get pods -n monitoring
```

Expected output (all pods `Running`):

```
NAME                                                      READY   STATUS
alloy-...                                                 2/2     Running
grafana-...                                               1/1     Running
loki-0                                                    2/2     Running
loki-gateway-...                                          1/1     Running
prometheus-kube-prom-stack-kube-prome-prometheus-0        2/2     Running
alertmanager-kube-prom-stack-kube-prome-alertmanager-0    2/2     Running
kube-prom-stack-kube-state-metrics-...                    1/1     Running
tempo-...                                                 1/1     Running
```

---

## Step 5 — Port-forward services to localhost

Run each in a separate terminal and keep them open while developing.

```bash
# Grafana UI
kubectl port-forward -n monitoring svc/grafana 3000:80

# Prometheus UI + query API
kubectl port-forward -n monitoring svc/kube-prom-stack-kube-prome-prometheus 9090:9090

# Alloy UI (component graph + live debugging)
kubectl port-forward -n monitoring svc/alloy 12345:12345

# Alloy — OTLP gRPC (traces + metrics push from agent)
kubectl port-forward -n monitoring svc/alloy 4317:4317

# Alloy — OTLP HTTP (alternative)
kubectl port-forward -n monitoring svc/alloy 4318:4318

# Loki — direct log push from otel_setup.py
kubectl port-forward -n monitoring svc/loki 3100:3100
```

---

## Step 6 — Open Grafana

URL: http://localhost:3000
Login: `admin` / `grafana`

> Change the password for any shared environment.

All four datasources (Prometheus, Loki, Tempo, Alertmanager) are pre-provisioned with
explicit UIDs so cross-signal navigation works out of the box:
- Traces → Logs (Tempo panel drills into Loki)
- Traces → Metrics (Tempo panel links to Prometheus)
- Logs → Traces (Loki log lines with `traceID=...` link to Tempo)
- Metrics exemplars link to Tempo traces

Two dashboards are pre-loaded under **Dashboards → Default**:
- Kubernetes Cluster (community id 7249)
- Node Exporter Full (community id 1860)

---

## Step 7 — Verify Prometheus scrape targets

Open http://localhost:9090/targets

You should see these jobs as **UP**:

| Job | Target | Source |
|-----|--------|--------|
| `loki` | `loki.monitoring.svc:3100` | Loki self-metrics |
| `tempo` | `tempo.monitoring.svc:3200` | Tempo self-metrics |
| `otel-agent-api` | `host.docker.internal:8000` | `agent_api.py` |
| `mcp-add-sub-server` | `host.docker.internal:8001` | `mcp_tool_instrumented.py add_sub` |
| `mcp-mul-div-server` | `host.docker.internal:8002` | `mcp_tool_instrumented.py mul_div` |

> `otel-agent-api`, `mcp-add-sub-server`, `mcp-mul-div-server` are only UP when those
> Python processes are running. Start them first with `python agent_api.py` and
> `python mcp_tool_instrumented.py add_sub / mul_div`.

### Docker Desktop note — expected DOWN targets

The following targets will always be `DOWN` on Docker Desktop and can be ignored.
These control-plane components bind their metrics to the node's loopback (`127.0.0.1`)
inside Docker Desktop's VM — unreachable from any pod. They are disabled in
`prometheus-values.yaml`:

```yaml
kubeControllerManager:
  enabled: false
kubeScheduler:
  enabled: false
kubeEtcd:
  enabled: false
kubeProxy:
  enabled: false
```

---

## Step 8 — Verify Alloy pipeline components

Open http://localhost:12345 (Alloy UI) or run:

```bash
curl -s http://localhost:12345/api/v0/web/components | \
  python -c "import sys,json; [print(f'[{c[\"health\"][\"state\"]}] {c[\"localID\"]}') for c in json.load(sys.stdin)]"
```

All components should be `[healthy]`:

| Component | Role |
|-----------|------|
| `otelcol.receiver.otlp.default` | Receives OTLP traces/metrics/logs on 4317/4318 |
| `otelcol.exporter.otlp.tempo` | Forwards traces → Tempo |
| `otelcol.exporter.prometheus.default` | Converts OTLP metrics → Prometheus format |
| `prometheus.remote_write.default` | Pushes metrics → Prometheus |
| `otelcol.exporter.loki.default` | Converts OTLP logs → Loki format |
| `loki.write.default` | Pushes logs → Loki |
| `discovery.kubernetes.pods` | Discovers all pods in the cluster |
| `loki.source.kubernetes.pods` | Tails logs from every pod → Loki |

---

## Signals flow

```
Agent process (localhost)
    │
    ├── Traces  → OTLP gRPC → localhost:4317 → Alloy → Tempo
    ├── Metrics → OTLP gRPC → localhost:4317 → Alloy → Prometheus (remote_write)
    │         OR Prometheus pull ← localhost:8000/8001/8002 ← Prometheus scrape
    └── Logs    → OTLP HTTP → localhost:4318 → Alloy → Loki
                OR HTTP push → localhost:3100 → Loki (direct, bypasses Alloy)

Kubernetes pods → Alloy (loki.source.kubernetes.pods) → Loki

Tempo (metrics_generator) → service-graphs + span-metrics → Prometheus (remote_write)
```

---

## Upgrading after config changes

```bash
helm upgrade kube-prom-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring --values prometheus-values.yaml

helm upgrade loki grafana/loki \
  --namespace monitoring --values loki-values.yaml

helm upgrade tempo grafana/tempo \
  --namespace monitoring --values tempo-values.yaml

helm upgrade alloy grafana/alloy \
  --namespace monitoring --values alloy-values.yaml

helm upgrade grafana grafana/grafana \
  --namespace monitoring --values grafana-values.yaml
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Grafana pod stuck in `Init:ErrImagePull` | `busybox:1.31.1` pull failure (Docker Hub rate limit) | `initChownData.enabled: false` in `grafana-values.yaml` |
| Loki target `DOWN` in Prometheus | ServiceMonitor disabled | `monitoring.serviceMonitor.enabled: true` in `loki-values.yaml` |
| OTLP metrics not appearing in Prometheus | Remote-write receiver off | `enableRemoteWriteReceiver: true` in `prometheus-values.yaml` |
| Traces→Logs / Traces→Metrics links broken in Grafana | Missing datasource UIDs | Add `uid: prometheus`, `uid: loki`, `uid: tempo` in `grafana-values.yaml` |
| Service map empty in Grafana | Tempo metrics_generator disabled | `metricsGenerator.enabled: true` in `tempo-values.yaml` |
| controller-manager / scheduler / etcd / proxy `DOWN` | Docker Desktop loopback binding | Disable in `prometheus-values.yaml` (see Step 7) |

---

## Teardown

```bash
helm uninstall grafana         -n monitoring
helm uninstall alloy           -n monitoring
helm uninstall tempo           -n monitoring
helm uninstall loki            -n monitoring
helm uninstall kube-prom-stack -n monitoring
kubectl delete namespace monitoring
```

> PersistentVolumeClaims are NOT deleted by `helm uninstall`.
> To fully clean up storage: `kubectl delete pvc --all -n monitoring`
