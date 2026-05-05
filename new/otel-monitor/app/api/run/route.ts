import { NextResponse } from 'next/server';

const AGENT_URL = process.env.AGENT_URL ?? 'http://localhost:8080';

// POST /api/run — Proxies a question to the orchestrator's POST /run.
// Keeps the browser same-origin (avoids CORS) and returns whatever the
// agent returned so the caller can show the answer.
export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  try {
    const res = await fetch(`${AGENT_URL}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`Agent API unreachable at ${AGENT_URL}:`, msg);
    return NextResponse.json(
      { error: `Agent API unreachable at ${AGENT_URL}` },
      { status: 503 },
    );
  }
}
