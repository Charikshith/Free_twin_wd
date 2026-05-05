import { NextResponse } from 'next/server';

const TEMPO_URL = 'http://localhost:3200';

interface TempoSearchResult {
  traceID: string;
  rootServiceName: string;
  rootTraceName: string;
  startTimeUnixNano: string;
  durationMs: number;
}

interface TempoTraceDetail {
  traceID: string;
  startTimeUnixNano: string;
  durationMs: number;
  batches: any[];
}

class TempoUnreachableError extends Error {
  constructor(cause: unknown) {
    super(`Tempo unreachable at ${TEMPO_URL}: ${cause instanceof Error ? cause.message : String(cause)}`);
    this.name = 'TempoUnreachableError';
  }
}

async function fetchTracesFromTempo(): Promise<TempoTraceDetail[]> {
  let searchRes: Response;
  try {
    searchRes = await fetch(`${TEMPO_URL}/api/search`, { cache: 'no-store' });
  } catch (err) {
    throw new TempoUnreachableError(err);
  }

  if (!searchRes.ok) {
    throw new TempoUnreachableError(`search returned HTTP ${searchRes.status}`);
  }

  const searchData = (await searchRes.json()) as { traces?: TempoSearchResult[] };
  const traceList = searchData.traces ?? [];
  if (traceList.length === 0) return [];

  const detailedTraces: TempoTraceDetail[] = [];
  for (const summary of traceList) {
    try {
      const traceRes = await fetch(`${TEMPO_URL}/api/traces/${summary.traceID}`, {
        cache: 'no-store',
      });
      if (!traceRes.ok) continue;
      const traceDetail = (await traceRes.json()) as any;
      detailedTraces.push({
        traceID: summary.traceID,
        startTimeUnixNano: summary.startTimeUnixNano,
        durationMs: summary.durationMs,
        batches: traceDetail.batches || [],
      });
    } catch (e) {
      console.warn(`Failed to fetch trace ${summary.traceID}:`, e);
    }
  }
  return detailedTraces;
}

export async function GET() {
  try {
    const traces = await fetchTracesFromTempo();
    return NextResponse.json({ traces });
  } catch (err: unknown) {
    if (err instanceof TempoUnreachableError) {
      // Surface a real error status so the client can preserve existing UI
      // state instead of treating it as "Tempo returned zero traces".
      console.error(err.message);
      return NextResponse.json({ error: err.message }, { status: 503 });
    }
    const msg = err instanceof Error ? err.message : String(err);
    console.error('Traces API error:', msg);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
