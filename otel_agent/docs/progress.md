All 4 DW Orchestrator KPIs are implemented. Here's what was added to agent_auto_multiple.py:

Metrics (Section 3)

┌───────────────────────────┬────────────────────────────────┬───────────────┬───────────────────────────────────┐
│            KPI            │             Metric             │     Type      │              Labels               │
├───────────────────────────┼────────────────────────────────┼───────────────┼───────────────────────────────────┤
│ Concurrent active workers │ orchestrator.active.workers    │ UpDownCounter │ worker_type                       │
├───────────────────────────┼────────────────────────────────┼───────────────┼───────────────────────────────────┤
│ Worker state transitions  │ orchestrator.state.transitions │ Counter       │ worker_type, from_state, to_state │
├───────────────────────────┼────────────────────────────────┼───────────────┼───────────────────────────────────┤
│ Orchestration error rate  │ orchestrator.errors            │ Counter       │ error_type, worker_type           │
├───────────────────────────┼────────────────────────────────┼───────────────┼───────────────────────────────────┤
│ Status sync failures      │ orchestrator.sync.failures     │ Counter       │ failure_type, worker_type         │
└───────────────────────────┴────────────────────────────────┴───────────────┴───────────────────────────────────┘

Tracing Spans

┌───────────────────────────────────────────────────┬──────────────────────────────────┬────────────────────────────────┐
│                       Span                        │              Where               │            Purpose             │
├───────────────────────────────────────────────────┼──────────────────────────────────┼────────────────────────────────┤
│ orchestrator.worker.lifecycle                     │ Wraps entire run_multi_agent     │ Full worker lifecycle (parent) │
├───────────────────────────────────────────────────┼──────────────────────────────────┼────────────────────────────────┤
│ orchestrator.transition (idle→running)            │ on_handoff callback              │ Tracks handoff start           │
├───────────────────────────────────────────────────┼──────────────────────────────────┼────────────────────────────────┤
│ orchestrator.transition (running→completed/error) │ After Runner.run completes/fails │ Tracks completion              │
├───────────────────────────────────────────────────┼──────────────────────────────────┼────────────────────────────────┤
│ orchestrator.sync                                 │ _sync_status_to_api()            │ Status sync to external API    │
└───────────────────────────────────────────────────┴──────────────────────────────────┴────────────────────────────────┘

Flow

1. Handoff fires → on_handoff records idle→running transition, increments active_workers
2. Run succeeds → records running→completed, decrements active_workers
3. Run fails → records running→error, decrements active_workers, increments orchestration_errors
4. Sync → _sync_status_to_api reports final status, tracks failures

#### Now in Grafana → Explore → Prometheus

Run these 4 queries one by one:

KPI 1 — State Transitions
orchestrator_state_transitions_total

KPI 2 — Active Workers
orchestrator_active_workers

KPI 3 — Transitions rate per minute
rate(orchestrator_state_transitions_total[5m]) * 60

KPI 4 — Error rate (will show 0 until an error occurs)
orchestrator_errors_total

Check http://localhost:9090/targets first — confirm calculator-agent is UP, then the queries above will return
data in Grafana.