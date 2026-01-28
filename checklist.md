Perfect — here’s a **clean, client-ready Deployment Checklist document** you can drop into Confluence, Notion, or a repo as `DEPLOYMENT_CHECKLIST.md`.

I’ve written it in a **practical, audit-friendly style** that works well with enterprise clients and SRE/Platform teams.

# 🧠 Multi-Agent System Deployment Checklist

**(MCP-based | Production Ready)**

**System Type:** Multi-Agent LLM System
**Scope:** Agents, Prompts, MCP Tools, Infrastructure
**Applies To:** Staging → Production Deployments

---

## 1. Pre-Deployment Readiness (MANDATORY)

### 1.1 Agent Configuration

* [ ] Agent roles clearly defined (planner, executor, critic, router, etc.)
* [ ] Agent graph/topology reviewed and documented
* [ ] No circular or unbounded agent loops
* [ ] Agent timeouts configured
* [ ] Retry limits configured per agent

### 1.2 Prompt & Agent Versioning

* [ ] Prompt versions are immutable and tagged
* [ ] Prompt changes reviewed and approved
* [ ] Prompt version mapped to agent name
* [ ] Previous stable prompt version recorded (rollback target)

### 1.3 MCP Tooling

* [ ] Tool versions pinned (no floating latest)
* [ ] Tool permissions reviewed (principle of least privilege)
* [ ] Tool timeouts and rate limits configured
* [ ] Tool failure modes defined (retry / fallback / abort)
* [ ] Tool contracts validated (input/output schema)

---

## 2. Testing & Quality Gates

### 2.1 Golden Dataset Validation

* [ ] Golden dataset updated and frozen
* [ ] Dataset represents real production traffic
* [ ] Edge cases and failure scenarios included
* [ ] All golden tests pass successfully
* [ ] Results compared against last production baseline

### 2.2 Automated Testing

* [ ] Unit tests for MCP tools pass
* [ ] Agent-level tests pass
* [ ] Deterministic runs verified (where applicable)
* [ ] LLM-as-judge evaluation scores within acceptable range

### 2.3 QA / Staging Validation

* [ ] Deployment tested in staging environment
* [ ] Shadow traffic validated (if enabled)
* [ ] Canary agent tested successfully
* [ ] Human QA review completed (sampled outputs)

---

## 3. Observability & Monitoring

### 3.1 KPIs Defined

* [ ] Task success rate baseline recorded
* [ ] Latency SLAs defined
* [ ] Cost per request baseline recorded
* [ ] Tool failure rate thresholds defined
* [ ] Quality score baseline defined

### 3.2 Telemetry

* [ ] OpenTelemetry tracing enabled
* [ ] Agent-level spans verified
* [ ] Tool call spans verified
* [ ] Error and timeout traces visible end-to-end

### 3.3 LLM Observability

* [ ] Langfuse traces enabled
* [ ] Prompt version tracking verified
* [ ] Token and cost tracking enabled
* [ ] Evaluation hooks configured

---

## 4. CI/CD Readiness

### 4.1 CI Pipeline

* [ ] Prompt linting checks pass
* [ ] Golden dataset regression checks pass
* [ ] KPI regression checks pass
* [ ] Security scans completed
* [ ] Build artifacts versioned and stored

### 4.2 CD Pipeline

* [ ] Deployment strategy selected (canary / blue-green)
* [ ] Canary percentage defined
* [ ] Auto-rollback conditions configured
* [ ] Deployment approvals completed

---

## 5. Production Safeguards

### 5.1 Runtime Controls

* [ ] Rate limits enforced per agent
* [ ] Global cost ceiling configured
* [ ] Per-request token limits enforced
* [ ] Emergency kill switch tested

### 5.2 Security & Compliance

* [ ] Secrets stored securely (vault / KMS)
* [ ] No secrets in prompts or logs
* [ ] Tool access audited
* [ ] Data retention policy enforced

---

## 6. Rollback Preparedness (CRITICAL)

### 6.1 Rollback Targets Identified

* [ ] Prompt version rollback available
* [ ] Tool version rollback available
* [ ] Model version rollback available
* [ ] Agent topology rollback available

### 6.2 Rollback Execution

* [ ] Rollback tested in staging
* [ ] Rollback does not require redeploying infra
* [ ] Rollback time < defined SLA
* [ ] Ownership assigned for rollback decision

---

## 7. Go-Live Checklist

* [ ] Deployment window approved
* [ ] On-call owner assigned
* [ ] Alerts enabled and tested
* [ ] Dashboards open and monitored
* [ ] Canary metrics stable for defined duration
* [ ] Full traffic enabled

---

## 8. Post-Deployment Validation (First 24–72 Hours)

* [ ] KPI comparison vs baseline
* [ ] Cost anomaly check
* [ ] Error and timeout review
* [ ] Human review sample completed
* [ ] No sustained KPI degradation observed

---

## 9. Incident Response (If KPIs Degrade)

* [ ] Identify affected agent(s)
* [ ] Identify prompt/tool/model version change
* [ ] Compare against historical traces
* [ ] Decide: rollback vs hotfix
* [ ] Document incident and resolution

---

## 10. Deployment Sign-Off

**Deployment Approved By:** ______________________
**Date:** ______________________
**Version Deployed:** ______________________

---

### Final Note (Optional for Client Docs)

> Multi-agent systems are production distributed systems.
> Every deployment must be observable, reversible, and measurable.

---
<!-- 
If you want next, I can:

* Convert this into a **one-page executive checklist**
* Create a **CI/CD YAML example**
* Add a **RACI table (who owns what)**
* Customize this for **regulated industries (finance/health)**

Just say the word 👍 -->


<!-- Perfect — this is the **heart of production safety** for agentic systems.
I’ll give you a **clear, step-by-step process**, same style as before: *who does what, in what order, with concrete artifacts*. -->


---

# 2. Testing & Quality Gates — Execution Process

Think of this as your **LLM Testing Pyramid**:

* Bottom → deterministic, automated
* Top → human judgment



**Process**
## 2.1 Golden Dataset Validation — Langfuse Process

---

### Step 1: Capture Production Traces

**Owner:** Platform / AI Engineers

**How in Langfuse**

* Instrument **every agent call**:

* Log:

  * Inputs
  * Outputs
  * Prompt version
  * Tool metadata
  * Latency & cost

Result:

* Langfuse automatically stores **high-fidelity production traces**

---

### Step 2: Create Golden Dataset from Traces

**Owner:** QA + Product

**How**

* In Langfuse UI:

  * Filter “successful” traces
  * Filter by agent name
  * Filter by tool usage or risk
* Select → **“Create Dataset”**

Best practice:

* Separate datasets:

  * `golden_happy_path`
  * `golden_edge_cases`
  * `golden_failures`

Each dataset item includes:

* Input
* Full agent trace
* Expected behavior (annotation)

---

### Step 3: Freeze Dataset Versions

**Owner:** QA

**How**

* Clone dataset → tag version

  * `golden_release_2026_01`
* Lock dataset for release
* No edits allowed until next cycle

Langfuse benefit:

* Dataset versioning is **native**
* Historical comparison is built-in

---

### Step 4: Run Dataset Evaluations

**Owner:** CI / AI Lead

**How**

* Use Langfuse **Dataset Runs**
* Execute with:

  * New prompt versions
  * Same tool versions
* Collect:

  * Output
  * Latency
  * Cost
  * Scores

---

### Step 5: Baseline Comparison

**Owner:** QA

**How**

* Compare:

  * Dataset run vs previous run
* Visualize:

  * Success rate delta
  * Score delta
  * Cost delta

Release rule:

* No statistically significant regression

---

## 2.2 Automated Testing — Process

### Goal

Catch **mechanical, structural, and quality issues** before human review.

---

### Step 1: Tool Tests (Outside Langfuse, Results Logged)

**Owner:** Backend

**How**

* Unit tests in CI
* Push pass/fail results as **Langfuse metadata**

Why:

* Langfuse keeps full release context

---

### Step 2: Agent-Level Tests

**Owner:** AI Engineer

**How**

* Run agent tests against mocked tools
* Log traces to Langfuse using:

  * `environment=ci`
  * `release_candidate=true`

You now get:

* Full visibility into agent decision paths
* Diffable traces between versions

---

### Step 3: Deterministic Verification

**Owner:** Platform

**How**

* Fix:

  * Model
  * Temperature
  * Tool mocks
* Re-run same dataset
* Compare traces:

  * Agent path should match
  * Only surface-level text variance allowed

Langfuse helps by:

* Showing **step-by-step trace diffs**

---

### Step 4: LLM-as-Judge in Langfuse

**Owner:** AI Lead

**How**

* Create **Evaluators** in Langfuse
* Define judge prompt:

  * correctness
  * safety
  * completeness
* Attach scores to each trace

Example gates:

* Mean score ≥ 4.2
* No score < 3 on critical tasks

---

## 2.3 QA / Staging Validation — Process

### Goal

Validate system behavior **in an environment that mirrors production**.

---
---

## Step 1: Staging Environment Tracing

**Owner:** Platform

**How**

* Deploy to staging
* Set:

  ```text
  LANGFUSE_ENV=staging
  ```
* All staging runs now grouped automatically

---

## Step 2: Shadow Traffic Analysis

**Owner:** SRE

**How**

* Mirror prod traffic to staging
* Compare:

  * Prod trace vs staging trace
* Langfuse lets you:

  * Filter by request ID
  * Compare outputs and scores

Critical rule:

* No side-effect tools allowed in shadow mode

---

## Step 3: Canary Agent Monitoring

**Owner:** SRE

**How**

* Route 1–5% traffic to new agent version
* Tag traces:

  ```text
  canary=true
  ```
* Create Langfuse dashboards:

  * Error rate
  * Score distribution
  * Cost

Auto-rollback trigger:

* Score drop > threshold
* Error spike

---

## Step 4: Human QA Review

**Owner:** QA

**How**

* Use Langfuse annotation UI
* Review sampled traces:

  * Approve
  * Flag
  * Comment

Langfuse becomes:

* QA evidence store
* Audit log

---

# Release Decision Using Langfuse (End-to-End)

| Gate             | Langfuse Feature  |
| ---------------- | ----------------- |
| Golden dataset   | Datasets          |
| Regression check | Dataset runs      |
| Agent behavior   | Traces            |
| Quality score    | Evaluators        |
| Human QA         | Annotations       |
| Canary           | Tags + dashboards |

---

# What You Gain by Doing It This Way

✅ One system of record
✅ No “where did this output come from?”
✅ Easy audits
✅ Confidence in prompt changes
✅ Fast rollback decisions

> Without Langfuse, teams argue.
> With Langfuse, teams **compare data**.

---

## 2.4 Quality Gate Enforcement (IMPORTANT)

### Release is BLOCKED if:

* Golden tests fail
* KPI regression exceeds threshold
* LLM-judge score drops below baseline
* Critical human QA issues found

### Release is ALLOWED if:

* All mandatory gates pass
* Exceptions are documented
* Rollback plan confirmed

---

# What This Gives You (Client Value)

✅ Predictable agent behavior
✅ No silent regressions
✅ Measurable quality improvements
✅ Confidence to deploy often

> This is how you make **agentic systems safe to scale**.

---

If you want, next I can:

* Create **example CI pipeline gates**
* Provide **LLM-as-judge prompt templates**
* Design a **golden dataset schema**
* Build a **QA scorecard**

Just tell me what you want next.
