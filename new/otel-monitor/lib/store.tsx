'use client';

import React, {
  createContext, useContext, useReducer, useCallback, useRef,
} from 'react';
import type { Trace, LogEntry, Alert, KpiState, TraceType, McpToolStats } from '@/types/telemetry';
import {
  generateTrace, createInitialKpi, MCP_TOOLS,
} from '@/lib/telemetry';
import {
  mapTempoTrace, deriveLogsFromTrace, deriveAlertsFromTrace,
  REAL_MCP_TOOLS, type RawTraceData,
} from '@/lib/tempo-mapper';

// ── State & Actions ─────────────────────────────────────────────────────────

interface TelemetryState {
  traces:  Trace[];
  logs:    LogEntry[];
  alerts:  Alert[];
  kpi:     KpiState;
  mode:    'real' | 'simulated';
}

type Action =
  | { type: 'INJECT_TRACE'; traceType: TraceType }
  | { type: 'SET_REAL_TRACES'; traces: Trace[]; logs: LogEntry[]; alerts: Alert[] }
  | { type: 'CLEAR_ALERTS' }
  | { type: 'SET_MODE'; mode: 'real' | 'simulated' };

function buildKpiFromTraces(traces: Trace[]): KpiState {
  const mcpCalls: Record<string, McpToolStats> = {};
  // Include both simulated and real MCP tools
  const allTools = [...MCP_TOOLS, ...REAL_MCP_TOOLS];
  const seen = new Set<string>();
  for (const t of allTools) {
    if (seen.has(t)) continue;
    seen.add(t);
    mcpCalls[t] = { calls: 0, errors: 0, totalMs: 0, history: [] };
  }

  let errors = 0;
  let promptTokens = 0;
  let compTokens = 0;
  const latencies: number[] = [];

  for (const trace of traces) {
    latencies.push(trace.dur);
    if (trace.status === 'ERROR') errors++;
    promptTokens += Number(trace.attrs['gen_ai.usage.prompt_tokens'] ?? 0);
    compTokens   += Number(trace.attrs['gen_ai.usage.completion_tokens'] ?? 0);

    for (const ch of trace.children) {
      // Count MCP invocations from the MCP-server-side spans only.
      // Openinference also emits orchestrator-side TOOL spans (with
      // `tool.name` attr) for the same invocation — counting those too
      // would double every tool call.
      let toolName = '';
      if (ch.name === 'add_operation')            toolName = 'add';
      else if (ch.name === 'subtract_operation')  toolName = 'subtract';
      else if (ch.name === 'solve_steps_operation') toolName = 'solve_steps';
      else if (ch.name.startsWith('mcp.'))        toolName = ch.name.replace('mcp.', '');

      if (toolName && mcpCalls[toolName]) {
        mcpCalls[toolName].calls++;
        mcpCalls[toolName].totalMs += ch.dur;
        if (ch.status === 'ERROR') mcpCalls[toolName].errors++;
      }
    }
  }

  // Build history snapshots
  for (const t of Object.keys(mcpCalls)) {
    mcpCalls[t].history = [mcpCalls[t].calls];
  }

  return {
    traces: traces.length,
    promptTokens,
    compTokens,
    errors,
    activeSpans: 0,
    latencies: latencies.slice(-50),
    mcpCalls,
  };
}

function reducer(state: TelemetryState, action: Action): TelemetryState {
  switch (action.type) {
    case 'INJECT_TRACE': {
      const { trace, logs, alerts, updatedKpi } = generateTrace(action.traceType, state.kpi);
      return {
        ...state,
        traces:  [trace, ...state.traces].slice(0, 100),
        logs:    [...logs, ...state.logs].slice(0, 300),
        alerts:  [...alerts, ...state.alerts].slice(0, 30),
        kpi:     updatedKpi,
      };
    }
    case 'SET_REAL_TRACES': {
      // Mirror Tempo's current state: `action.traces` is the authoritative
      // full set from the latest poll. Replacing (not merging) ensures the
      // UI drops traces that Tempo has evicted from its retention window.
      const traces = action.traces.slice(0, 100);
      const kpi = buildKpiFromTraces(traces);
      return {
        ...state,
        traces,
        logs:    [...action.logs, ...state.logs].slice(0, 300),
        alerts:  [...action.alerts, ...state.alerts].slice(0, 30),
        kpi,
      };
    }
    case 'SET_MODE':
      return { ...state, mode: action.mode };
    case 'CLEAR_ALERTS':
      return { ...state, alerts: [] };
    default:
      return state;
  }
}

function buildInitialState(): TelemetryState {
  return {
    traces: [], logs: [], alerts: [], kpi: createInitialKpi(), mode: 'real',
  };
}

// ── Context ─────────────────────────────────────────────────────────────────

interface TelemetryContextValue {
  state:       TelemetryState;
  injectTrace: (type: TraceType) => void;
  clearAlerts: () => void;
  setMode:     (mode: 'real' | 'simulated') => void;
}

const TelemetryContext = createContext<TelemetryContextValue | null>(null);

// Returns null when the backend is unreachable — the caller should preserve
// existing UI state rather than clearing it. Returns an empty array only when
// Tempo legitimately has no traces.
async function fetchRealTraces(): Promise<
  { traces: Trace[]; logs: LogEntry[]; alerts: Alert[] } | null
> {
  let res: Response;
  try {
    res = await fetch('/api/traces', { cache: 'no-store' });
  } catch {
    return null;
  }
  if (!res.ok) return null;

  const data = (await res.json()) as { traces?: RawTraceData[] };
  const rawTraces = data.traces ?? [];

  const traces: Trace[] = [];
  const logs: LogEntry[] = [];
  const alerts: Alert[] = [];

  for (const raw of rawTraces) {
    const trace = mapTempoTrace(raw);
    if (trace) {
      traces.push(trace);
      logs.push(...deriveLogsFromTrace(trace));
      alerts.push(...deriveAlertsFromTrace(trace));
    }
  }

  return { traces, logs, alerts };
}

export function TelemetryProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, buildInitialState);

  const injectTrace = useCallback((type: TraceType) => {
    dispatch({ type: 'INJECT_TRACE', traceType: type });
  }, []);

  const clearAlerts = useCallback(() => {
    dispatch({ type: 'CLEAR_ALERTS' });
  }, []);

  const setMode = useCallback((mode: 'real' | 'simulated') => {
    dispatch({ type: 'SET_MODE', mode });
  }, []);

  const stateRef = useRef(state);
  stateRef.current = state;

  const seenTraceIds = useRef(new Set<string>());

  // Poll real traces from Tempo every 4 seconds. Only dispatches on a
  // successful response; a null (Tempo unreachable) skips the dispatch so
  // the UI keeps showing the last-known-good state instead of flickering
  // to empty on every transient connection error.
  React.useEffect(() => {
    const syncFromTempo = async () => {
      const result = await fetchRealTraces();
      if (result === null) return;
      const { traces, logs, alerts } = result;
      const newIds = traces
        .map(t => t.traceId)
        .filter(id => !seenTraceIds.current.has(id));
      newIds.forEach(id => seenTraceIds.current.add(id));
      const shortNew = new Set(newIds.map(id => id.slice(0, 8)));
      const newLogs = logs.filter(l => shortNew.has(l.traceId));
      const newAlerts = alerts.filter(a =>
        Array.from(shortNew).some(s => a.desc?.includes(s)),
      );
      dispatch({ type: 'SET_REAL_TRACES', traces, logs: newLogs, alerts: newAlerts });
    };

    syncFromTempo();

    const id = setInterval(() => {
      if (stateRef.current.mode !== 'real') return;
      syncFromTempo();
    }, 4000);
    return () => clearInterval(id);
  }, []);

  // Simulated auto-emit when in simulated mode
  React.useEffect(() => {
    if (state.mode !== 'simulated') return;
    const TYPES: TraceType[] = ['normal','normal','normal','normal','multi','slow','error'];
    const id = setInterval(() => {
      const weights = [0.55, 0.55, 0.55, 0.55, 0.15, 0.10, 0.08];
      const r = Math.random();
      let cum = 0;
      let pick: TraceType = 'normal';
      for (let i = 0; i < TYPES.length; i++) {
        cum += weights[i];
        if (r < cum) { pick = TYPES[i]; break; }
      }
      dispatch({ type: 'INJECT_TRACE', traceType: pick });
    }, 2200);
    return () => clearInterval(id);
  }, [state.mode]);

  return (
    <TelemetryContext.Provider value={{ state, injectTrace, clearAlerts, setMode }}>
      {children}
    </TelemetryContext.Provider>
  );
}

export function useTelemetry() {
  const ctx = useContext(TelemetryContext);
  if (!ctx) throw new Error('useTelemetry must be used within TelemetryProvider');
  return ctx;
}
