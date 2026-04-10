# ⚡ FlowLog — Distributed Tracing & Logging Platform

> A production-grade distributed tracing and logging platform that captures real-time application flow, function-level traces, and structured logs across any application — similar to Datadog APM or Jaeger, built from scratch.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Go](https://img.shields.io/badge/Go-1.22+-00ADD8.svg)](https://go.dev)
[![Kafka](https://img.shields.io/badge/Apache_Kafka-7.4.0-231F20.svg)](https://kafka.apache.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)](https://postgresql.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 Table of Contents

- [What is FlowLog?](#what-is-flowlog)
- [The Problem It Solves](#the-problem-it-solves)
- [Live Demo](#live-demo)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Components Deep Dive](#components-deep-dive)
  - [Python SDK](#1-python-sdk)
  - [Ingestion API](#2-ingestion-api)
  - [Kafka Message Queue](#3-kafka-message-queue)
  - [Go Log Processor](#4-go-log-processor)
  - [PostgreSQL Schema](#5-postgresql-schema)
  - [Query API](#6-query-api)
  - [Dashboard](#7-dashboard)
- [Getting Started](#getting-started)
- [SDK Integration Guide](#sdk-integration-guide)
- [API Reference](#api-reference)
- [Load Testing Results](#load-testing-results)
- [Key Engineering Decisions](#key-engineering-decisions)
- [What I Learned](#what-i-learned)

---

## What is FlowLog?

FlowLog is a **distributed tracing and logging platform** that automatically captures the full execution flow of any application. When integrated via the Python SDK, it records every function call — the exact file, function name, line number, execution duration, success/failure status, and error details — and links them all together under a single **Trace ID** per request.

This means when something breaks in production, you don't guess. You open FlowLog, find the trace, and immediately see the exact function, file, and line where it failed — along with every function that ran before it.

**Think of it as CCTV cameras for your application's code.**

---

## The Problem It Solves

### Before FlowLog

```
Production alert: "App is slow / broken"

Developer opens laptop:
  - Which service is broken?
  - Which function failed?
  - What was the request doing before it failed?
  - Was it the database? The scraper? The auth layer?

Result: Hours of debugging, adding print statements,
        reading random log files, still not sure.
```

### After FlowLog

```
Production alert: "App is slow / broken"

Developer opens FlowLog dashboard:

Trace: abc-123  |  POST /deals  |  FAILED  |  8.4s

  1. auth_middleware()   auth.py:23       12ms   ✅ SUCCESS
  2. get_user()          users.py:45      8ms    ✅ SUCCESS
  3. fetch_deals()       scraper.py:89    180ms  ✅ SUCCESS
  4. parse_deals()       parser.py:34     45ms   ✅ SUCCESS
  5. save_to_db()        database.py:201  8187ms ❌ FAILED
       └── ConnectionTimeout: Could not connect to PostgreSQL
           Stack trace: line 201 in save_to_db()

Result: Root cause identified in 10 seconds.
```

---

## Live Demo

### Dashboard Screenshot

The FlowLog dashboard shows:
- **Left panel**: All traces with SUCCESS/FAILED status, span count, and timestamp
- **Stats bar**: Total traces, successful, and failed counts
- **Right panel**: Full function call flow with file, function, line number, duration
- **Error details**: Expandable error box with error type, message, and stack trace

### Example Trace Response

```json
{
  "trace_id": "test-trace-005",
  "status": "FAILED",
  "created_at": "2026-04-10T06:00:55",
  "flow": [
    {
      "function_name": "auth_middleware",
      "file_name": "auth.py",
      "line_number": 23,
      "duration_ms": 12,
      "status": "SUCCESS",
      "span_order": 1,
      "error": null
    },
    {
      "function_name": "fetch_deals",
      "file_name": "scraper.py",
      "line_number": 89,
      "duration_ms": 180,
      "status": "SUCCESS",
      "span_order": 2,
      "error": null
    },
    {
      "function_name": "save_to_db",
      "file_name": "database.py",
      "line_number": 201,
      "duration_ms": 8187,
      "status": "FAILED",
      "span_order": 3,
      "error": {
        "error_type": "ConnectionTimeout",
        "error_message": "Could not connect to PostgreSQL",
        "stack_trace": "line 201 in save_to_db"
      }
    }
  ]
}
```

---

## Architecture

### High Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        YOUR APPLICATION                              │
│                                                                      │
│   from flowlog_sdk import trace, init                               │
│   init(api_url="http://localhost:8000", api_key="xxx")              │
│                                                                      │
│   @trace                    @trace                    @trace        │
│   def auth():               def fetch():              def save():   │
│       ...                       ...                       ...       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │  POST /ingest/span
                               │  (batch of spans with trace_id)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FLOWLOG PLATFORM                                 │
│                                                                      │
│  ┌─────────────────────┐                                            │
│  │   Ingestion API      │  ← FastAPI, load balanced via K8s         │
│  │   (FastAPI :8000)    │    Validates API key                      │
│  │                      │    Returns 200 OK immediately             │
│  └──────────┬───────────┘                                           │
│             │                                                        │
│             │  Produces message                                      │
│             ▼                                                        │
│  ┌─────────────────────┐                                            │
│  │      KAFKA           │  ← Message queue buffer                   │
│  │  Topic: raw-logs     │    3 partitions                           │
│  │  (port 9092)         │    Zookeeper managed                      │
│  │                      │    Never drops messages                   │
│  └──────────┬───────────┘                                           │
│             │                                                        │
│             │  Consumes messages                                     │
│             ▼                                                        │
│  ┌─────────────────────┐                                            │
│  │   Log Processor      │  ← Written in Go                          │
│  │   (Go service)       │    Goroutines for concurrency             │
│  │                      │    Consumer group: flowlog-processors     │
│  └──────────┬───────────┘                                           │
│             │                                                        │
│             ├──────────────────────┐                                │
│             ▼                      ▼                                │
│  ┌──────────────────┐  ┌──────────────────────┐                    │
│  │   PostgreSQL      │  │   Azure Blob / S3     │                   │
│  │   (port 5433)     │  │   Raw log archival    │                   │
│  │                   │  │   Cold storage        │                   │
│  │   - apps          │  └──────────────────────┘                   │
│  │   - traces        │                                              │
│  │   - spans         │                                              │
│  │   - errors        │                                              │
│  └──────────┬────────┘                                              │
│             │                                                        │
│             ▼                                                        │
│  ┌─────────────────────┐                                            │
│  │    Query API         │  ← FastAPI :8001                          │
│  │    (FastAPI :8001)   │    SQLAlchemy ORM                         │
│  │                      │    Trace reconstruction                   │
│  │  GET /traces         │    Filter by app, status, time            │
│  │  GET /traces/:id     │                                           │
│  │  GET /spans          │                                           │
│  └──────────┬───────────┘                                           │
│             │                                                        │
│             ▼                                                        │
│  ┌─────────────────────┐                                            │
│  │    Dashboard         │  ← Plain HTML/CSS/JS                      │
│  │    (index.html)      │    Fetches from Query API                 │
│  │                      │    Auto-refreshes every 10s               │
│  │  - Trace list        │    Click to drill down                    │
│  │  - Flow visualization│                                           │
│  │  - Error details     │                                           │
│  └─────────────────────┘                                            │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              INFRASTRUCTURE                                   │   │
│  │  Docker Compose  │  Kubernetes  │  GitHub Actions CI/CD      │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow Explained

```
Step 1: Developer decorates functions with @trace
        ↓
Step 2: SDK generates Trace ID for each request (uuid4)
        Stores in threading.local() — isolated per thread
        ↓
Step 3: Each function call creates a "span":
        {
          trace_id: "abc-123",      ← links all spans of one request
          function_name: "fetch",   ← captured via inspect module
          file_name: "scraper.py",  ← captured via inspect module
          line_number: 89,          ← captured via inspect module
          duration_ms: 142,         ← measured with time.time()
          status: "SUCCESS/FAILED", ← try/except wrapper
          span_order: 1             ← incremented per request
        }
        ↓
Step 4: SDK sends span to Ingestion API (async, timeout=2s)
        Never blocks the developer's application
        ↓
Step 5: Ingestion API validates API key
        Pushes to Kafka topic "raw-logs"
        Returns 200 OK immediately
        ↓
Step 6: Go processor reads from Kafka
        Spawns goroutine per message (concurrent processing)
        Writes to PostgreSQL:
          - apps table (get or create)
          - traces table (get or create by trace_id)
          - spans table (insert span)
          - errors table (insert if FAILED)
        ↓
Step 7: Query API reads from PostgreSQL
        Reconstructs full trace by joining spans on trace_id
        Orders spans by span_order
        Returns complete flow
        ↓
Step 8: Dashboard fetches from Query API every 10 seconds
        Renders trace list and flow visualization
```

### Database Schema

```
┌─────────────────────────────────────────────────────────┐
│                      apps                               │
│  id (UUID PK) │ name │ api_key │ created_at            │
└───────────────────────┬─────────────────────────────────┘
                        │ 1 app has many traces
                        ▼
┌─────────────────────────────────────────────────────────┐
│                     traces                              │
│  id (UUID PK) │ trace_id (UNIQUE) │ app_id (FK)        │
│  endpoint │ total_duration_ms │ status │ created_at    │
└───────────────────────┬─────────────────────────────────┘
                        │ 1 trace has many spans
                        ▼
┌─────────────────────────────────────────────────────────┐
│                      spans                              │
│  id (UUID PK) │ trace_id (FK) │ function_name          │
│  file_name │ line_number │ duration_ms │ status        │
│  span_order │ metadata (JSONB) │ created_at            │
└───────────────────────┬─────────────────────────────────┘
                        │ 1 span has at most 1 error
                        ▼
┌─────────────────────────────────────────────────────────┐
│                      errors                             │
│  id (UUID PK) │ span_id (FK) │ error_type             │
│  error_message │ stack_trace │ created_at             │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Technology | Version | Role | Why This Tech |
|---|---|---|---|
| **Python** | 3.11+ | SDK + APIs | Widespread backend language, clean decorator syntax |
| **FastAPI** | 0.104+ | Ingestion + Query APIs | Async, fast, automatic OpenAPI docs |
| **SQLAlchemy** | 2.0+ | ORM for PostgreSQL | Clean model definitions, relationship management |
| **Apache Kafka** | 7.4.0 | Message queue | Handles 100k+ msgs/sec, fault tolerant, offset tracking |
| **Zookeeper** | 7.4.0 | Kafka coordinator | Manages brokers, topics, consumer offsets |
| **Go** | 1.22+ | Log processor | True concurrency via goroutines, no GIL limitation |
| **PostgreSQL** | 15 | Primary database | Relational, JSONB support, strong indexing |
| **Docker Compose** | Latest | Local orchestration | One command to run all services |
| **Kubernetes** | Latest | Production orchestration | Auto-scaling, self-healing deployments |
| **GitHub Actions** | Latest | CI/CD pipeline | Automated test and deploy on every push |
| **Locust** | Latest | Load testing | Python-based, real concurrent user simulation |
| **Pydantic** | 2.0+ | Request validation | Automatic validation and serialization |

---

## Project Structure

```
flowlog/
│
├── sdk/                          # Python SDK — integrate into any app
│   ├── flowlog_sdk/
│   │   ├── __init__.py           # Public API: trace, init
│   │   ├── tracer.py             # Trace ID generation, threading.local storage
│   │   └── decorator.py         # @trace decorator, span capture logic
│   ├── test_sdk.py               # SDK integration test
│   └── requirements.txt
│
├── ingestion-api/                # FastAPI — receives spans from SDK
│   ├── main.py                   # API endpoints: /register, /ingest/span
│   ├── models.py                 # Pydantic request/response models
│   └── requirements.txt
│
├── log-processor/                # Go service — Kafka consumer
│   ├── main.go                   # Entry point, config, DB init
│   ├── consumer.go               # Kafka reader, goroutine spawner
│   ├── processor.go              # PostgreSQL writes, span/trace/error logic
│   ├── go.mod
│   └── go.sum
│
├── query-api/                    # FastAPI — read and query logs
│   ├── main.py                   # API endpoints: /traces, /spans
│   ├── models.py                 # SQLAlchemy ORM models
│   ├── database.py               # PostgreSQL connection, session management
│   └── requirements.txt
│
├── dashboard/
│   └── index.html                # Single-file dashboard — HTML/CSS/JS
│
├── database/
│   └── schema.sql                # PostgreSQL schema — all 4 tables + indexes
│
├── loadtest/
│   └── locustfile.py             # Locust load test scenarios
│
├── k8s/                          # Kubernetes manifests
│   ├── ingestion-api.yaml
│   ├── query-api.yaml
│   └── log-processor.yaml
│
├── .github/
│   └── workflows/
│       └── ci.yml                # GitHub Actions CI/CD pipeline
│
└── docker-compose.yml            # Local dev: Kafka + Zookeeper + PostgreSQL
```

---

## Components Deep Dive

### 1. Python SDK

The SDK is a Python library developers install in their application. It uses Python's `inspect` module and decorator pattern to automatically capture trace data without modifying existing code logic.

**Key Concepts:**

**Decorator Pattern:**
```python
@trace
def fetch_deals():
    return scrape_reddit()
```
The `@trace` decorator wraps the function. Before the function runs — it captures metadata. After it runs (success or failure) — it sends the span to the Ingestion API.

**Trace ID Propagation:**
```python
# threading.local() stores data per-thread
# 100 simultaneous requests = 100 independent trace IDs
_local = threading.local()

def get_current_trace_id():
    return getattr(_local, 'trace_id', None)
```

**is_root Pattern:**
```python
is_root = get_current_trace_id() is None

if is_root:
    # First function in this request — generate new trace ID
    trace_id = generate_trace_id()
    set_current_trace_id(trace_id)
else:
    # Subsequent function — reuse existing trace ID
    trace_id = get_current_trace_id()
```

This ensures all functions in one request share the same `trace_id`, while different requests get different IDs.

**Automatic Metadata Capture:**
```python
# Python's inspect module gives us code metadata at runtime
source = inspect.getsourcefile(func)       # file path
lines, start_line = inspect.getsourcelines(func)  # line number
func.__name__                               # function name
```

**Fire and Forget:**
```python
# SDK sends span with 2 second timeout
# Never blocks the developer's application
requests.post(
    f"{_api_url}/ingest/span",
    json=span,
    headers={"X-API-Key": _api_key},
    timeout=2
)
```

---

### 2. Ingestion API

Built with FastAPI. Its only job is to receive spans from the SDK, validate them, and push them to Kafka as fast as possible.

**Why FastAPI:**
- Async by default — handles many concurrent connections
- Pydantic validation — automatically validates every incoming request
- Auto-generated OpenAPI docs at `/docs`

**The Critical Design Decision — No Direct DB Writes:**
```
SDK → Ingestion API → Kafka  ✅ CORRECT
SDK → Ingestion API → PostgreSQL  ❌ WRONG
```

If the API wrote directly to PostgreSQL:
- Slow — DB writes take 10-50ms
- Fragile — if DB is slow, API is slow
- Not scalable — DB becomes bottleneck

By writing to Kafka first:
- API returns in < 5ms always
- DB can be slow — messages wait in Kafka
- Horizontally scalable — add more API instances freely

**Kafka Producer:**
```python
producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Drop message into Kafka — instant, non-blocking
producer.send("raw-logs", value=message)
producer.flush()
```

---

### 3. Kafka Message Queue

Kafka is the backbone of FlowLog's reliability story. It acts as a buffer between the ingestion layer and the processing layer.

**Topic Configuration:**
```
Topic: raw-logs
Partitions: 3
Replication Factor: 1 (development) / 3 (production)
```

**Why 3 Partitions:**
3 partitions means up to 3 consumers can read in parallel. If one Go processor instance can't keep up — spin up 2 more, each reads a different partition. Linear scaling.

**Offset Tracking:**
Every message in Kafka has an offset (a sequence number). The Go processor commits its offset after processing each message. If it crashes and restarts — it continues from exactly where it left off. No messages are lost, no messages are processed twice.

```
Partition 0: [msg(0), msg(1), msg(2), msg(3), msg(4)...]
                                              ↑
                              consumer committed here
                              on restart: continue from msg(4)
```

**Zookeeper's Role:**
Zookeeper manages Kafka's internal state:
- Tracks which brokers are alive
- Stores topic and partition metadata  
- Tracks consumer group offsets
- Handles leader election for partitions

---

### 4. Go Log Processor

The Go processor is the most performance-critical component. It reads messages from Kafka and writes them to PostgreSQL as fast as possible.

**Why Go (Not Python):**
Python has the GIL (Global Interpreter Lock) — only one thread runs at a time. Go has true concurrency via goroutines.

```
Python: process 1000 messages → one by one → slow
Go:     process 1000 messages → 1000 goroutines → all at once → fast
```

**Goroutine Per Message:**
```go
for {
    msg, _ := reader.ReadMessage(context.Background())
    
    // Spawn goroutine — this is Go's superpower
    // Each message processed concurrently
    wg.Add(1)
    go func(s SpanMessage) {
        defer wg.Done()
        processSpan(db, s)
    }(span)
}
```

**Processing Logic Per Span:**
```
1. getOrCreateApp()    → INSERT app if not exists, get ID
2. getOrCreateTrace()  → INSERT trace if not exists (ON CONFLICT DO NOTHING)
3. insertSpan()        → INSERT span with all metadata
4. insertError()       → INSERT error if span.status == "FAILED"
5. updateTraceStatus() → UPDATE trace to FAILED if any span failed
```

**ON CONFLICT Pattern:**
```sql
INSERT INTO traces (trace_id, app_id, status)
VALUES ($1, $2, 'SUCCESS')
ON CONFLICT (trace_id) DO NOTHING
```
Multiple spans from the same trace arrive concurrently. `ON CONFLICT DO NOTHING` ensures the trace row is only created once even if 10 goroutines try simultaneously.

---

### 5. PostgreSQL Schema

Four tables with carefully designed relationships and indexes.

**UUID Primary Keys:**
```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid()
```
UUIDs instead of sequential integers because:
- Safe for distributed systems — no collision risk
- No sequential ID leakage — security benefit
- Works across multiple database instances

**JSONB for Metadata:**
```sql
metadata JSONB
```
JSONB (binary JSON) stores arbitrary key-value metadata per span. Developers can attach custom data:
```python
@trace
def fetch_deals(subreddit):
    # FlowLog captures this automatically
    # Developer can add metadata via SDK
    return results
```

**Indexes for Query Performance:**
```sql
CREATE INDEX idx_traces_app_id ON traces(app_id);
CREATE INDEX idx_traces_created_at ON traces(created_at);
CREATE INDEX idx_spans_trace_id ON spans(trace_id);
CREATE INDEX idx_errors_span_id ON errors(span_id);
```
Without indexes — every query scans the entire table. With indexes — queries jump directly to matching rows. Critical when you have millions of spans.

---

### 6. Query API

The Query API reads from PostgreSQL and reconstructs full traces. Built with FastAPI + SQLAlchemy.

**SQLAlchemy Relationships:**
```python
class Trace(Base):
    spans = relationship("Span", back_populates="trace",
                        order_by="Span.span_order")
```
Defining the relationship means SQLAlchemy automatically joins and orders spans when you load a trace. No manual JOIN queries needed.

**Trace Reconstruction:**
```python
# One query loads the trace AND all its spans (via relationship)
trace = db.query(Trace).filter(Trace.trace_id == trace_id).first()

# Spans are already ordered by span_order
for span in trace.spans:
    # Build the flow — each span is one function call
    flow.append({
        "function_name": span.function_name,
        "file_name": span.file_name,
        "line_number": span.line_number,
        ...
    })
```

**Filtering:**
```python
# Filter by app name, status, time window
GET /traces?app_name=dealhunter&status=FAILED&hours=1
GET /spans?function_name=save_to_db&status=FAILED
```

---

### 7. Dashboard

Single-file HTML/CSS/JavaScript dashboard. No framework, no build step.

**Auto-Refresh:**
```javascript
// Polls Query API every 10 seconds
loadTraces();
setInterval(loadTraces, 10000);
```

**Trace Flow Rendering:**
Each span renders as a card with a colored dot (green = SUCCESS, red = FAILED) connected by a vertical line — visually showing the execution flow from top to bottom.

**Click to Expand:**
Each span card is clickable — expands to show full details including file name, line number, duration, timestamp, and error details if failed.

---

## Getting Started

### Prerequisites

- Docker Desktop
- Python 3.11+
- Go 1.22+
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/YashDayma55/Flowlog.git
cd Flowlog
```

### 2. Start Infrastructure

```bash
docker-compose up
```

This starts:
- PostgreSQL on port 5433
- Kafka on port 9092
- Zookeeper on port 2181

Wait 30 seconds for all services to be healthy.

### 3. Create Database Schema

```bash
Get-Content database/schema.sql | docker exec -i flowlog-postgres psql -U flowlog -d flowlog
```

### 4. Create Kafka Topic

```bash
docker exec -it flowlog-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic raw-logs --partitions 3 --replication-factor 1
```

### 5. Start Ingestion API

```bash
cd ingestion-api
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 6. Start Go Log Processor

```bash
cd log-processor
go run main.go consumer.go processor.go
```

### 7. Start Query API

```bash
cd query-api
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

### 8. Open Dashboard

Open `dashboard/index.html` in your browser.

### 9. Verify Everything Works

```bash
# Register an app
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"name": "myapp"}'

# Send a test span (use API key from above)
curl -X POST http://localhost:8000/ingest/span \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "trace_id": "test-001",
    "function_name": "fetch_data",
    "file_name": "app.py",
    "line_number": 42,
    "duration_ms": 120,
    "status": "SUCCESS",
    "span_order": 1
  }'

# Query the trace
curl http://localhost:8001/traces/test-001
```

---

## SDK Integration Guide

### Install SDK

```bash
pip install requests  # only dependency
# Copy sdk/flowlog_sdk/ into your project
```

### Initialize

```python
from flowlog_sdk import trace, init

# Call once at application startup
init(
    api_url="http://localhost:8000",
    api_key="your-api-key-from-register"
)
```

### Decorate Functions

```python
@trace
def auth_middleware(token):
    user = verify_token(token)
    return user

@trace
def fetch_deals(subreddit):
    posts = reddit_api.get_posts(subreddit)
    return posts

@trace
def save_to_db(deals):
    db.bulk_insert(deals)
    return True
```

### That's It

Every decorated function now automatically captures:
- Function name, file name, line number
- Execution duration
- Success or failure status
- Full error details and stack trace on failure
- Links all functions of one request by Trace ID

---

## API Reference

### Ingestion API (port 8000)

#### Register Application
```
POST /register
Content-Type: application/json

{
  "name": "your-app-name"
}

Response:
{
  "app_name": "your-app-name",
  "api_key": "uuid-api-key",
  "message": "Save this API key"
}
```

#### Ingest Span
```
POST /ingest/span
Content-Type: application/json
X-API-Key: your-api-key

{
  "trace_id": "unique-trace-id",
  "function_name": "fetch_deals",
  "file_name": "scraper.py",
  "line_number": 89,
  "duration_ms": 142,
  "status": "SUCCESS",
  "span_order": 1,
  "error": null,
  "metadata": {}
}

Response:
{
  "status": "accepted",
  "trace_id": "unique-trace-id"
}
```

### Query API (port 8001)

#### List Traces
```
GET /traces?app_name=dealhunter&status=FAILED&hours=24&limit=50

Response:
{
  "total": 3,
  "traces": [
    {
      "trace_id": "abc-123",
      "status": "FAILED",
      "endpoint": null,
      "total_duration_ms": null,
      "created_at": "2026-04-10T06:00:55",
      "span_count": 3
    }
  ]
}
```

#### Get Full Trace
```
GET /traces/{trace_id}

Response:
{
  "trace_id": "abc-123",
  "status": "FAILED",
  "flow": [
    {
      "function_name": "auth_middleware",
      "file_name": "auth.py",
      "line_number": 23,
      "duration_ms": 12,
      "status": "SUCCESS",
      "span_order": 1,
      "error": null
    },
    ...
  ]
}
```

#### Search Spans
```
GET /spans?function_name=save_to_db&status=FAILED&limit=50

Response:
{
  "total": 5,
  "spans": [...]
}
```

---

## Load Testing Results

Load tested with **Locust** simulating 100 concurrent users continuously sending spans.

### Results

| Metric | Value |
|---|---|
| **Total Requests** | 37,016 |
| **Requests Per Second** | 177.83 RPS |
| **Failure Rate** | 0% |
| **Median Latency** | 190ms |
| **p95 Latency** | 400ms |
| **p99 Latency** | 510ms |
| **Min Latency** | 6ms |
| **Max Latency** | 927ms |
| **Concurrent Users** | 100 |

### What These Numbers Mean

- **177 RPS** — the system processed 177 span ingestion requests every second
- **0% failures** — zero requests dropped or errored across 37,000 requests
- **190ms median** — half of all requests completed in under 190ms end-to-end
- **p95 400ms** — 95% of requests completed in under 400ms

### Bottleneck Analysis

The `/register` endpoint showed higher latency (2200ms median) due to:
- In-memory app registry lookup
- UUID generation

This is not a production concern — registration happens once per app startup, not per request. The critical path (`/ingest/span`) maintained 190ms median consistently.

---

## Key Engineering Decisions

### 1. Kafka as Buffer (Not Direct DB Writes)

**Decision:** Ingestion API → Kafka → Go Processor → PostgreSQL

**Why:** Decouples ingestion speed from write speed. The ingestion API returns in < 5ms regardless of database load. Kafka absorbs traffic spikes. If the database goes down for 60 seconds — no spans are lost, they queue in Kafka and flush when DB recovers.

### 2. Go for the Log Processor (Not Python)

**Decision:** Log processor written in Go with goroutines

**Why:** Python's GIL prevents true parallelism. Go goroutines are genuinely concurrent — 1000 spans can be processed simultaneously. For a component whose only job is read → transform → write as fast as possible, Go is the right tool.

### 3. threading.local() for Trace ID Storage

**Decision:** Store trace ID in thread-local storage, not a global variable

**Why:** A global variable would be overwritten by concurrent requests. threading.local() gives each thread its own independent storage. 100 simultaneous requests = 100 independent trace IDs, never mixing.

### 4. UUID Primary Keys (Not Sequential Integers)

**Decision:** All primary keys are UUIDs

**Why:** In a distributed system with multiple writer instances, sequential integers cause collisions. UUIDs are generated independently on any machine with no coordination needed and zero collision risk.

### 5. ON CONFLICT DO NOTHING for Trace Creation

**Decision:** Use PostgreSQL upsert pattern for trace creation

**Why:** Multiple spans from the same trace arrive concurrently via different Kafka partitions. Without this, multiple goroutines would try to INSERT the same trace_id simultaneously, causing unique constraint violations. ON CONFLICT DO NOTHING makes it idempotent.

### 6. Separate Ingestion and Query APIs

**Decision:** Two separate FastAPI services on different ports

**Why:** Read and write workloads have different characteristics. The ingestion API needs to be optimized for high write throughput. The query API needs complex joins and filtering. Separating them allows independent scaling — if dashboard usage spikes, scale query API without touching ingestion.

---

## What I Learned

Building FlowLog from scratch taught me:

**Distributed Systems:**
- How Kafka's producer/consumer model decouples services
- How Zookeeper manages distributed coordination
- How offset tracking enables fault tolerance
- Why message queues are critical for reliability

**Concurrency:**
- Go's goroutine model vs Python's GIL limitation
- How threading.local() isolates state per thread
- How to handle concurrent database writes safely

**Backend Architecture:**
- Why separating read and write APIs matters
- How to design schemas for tracing systems
- The importance of indexes for query performance
- Why UUID keys are better than integers in distributed systems

**DevOps:**
- Docker Compose for local multi-service orchestration
- How CORS works and why browsers enforce it
- Port mapping in containerized environments
- CI/CD pipeline design with GitHub Actions

---

## Author

**Yash Dayma**
- GitHub: [@YashDayma55](https://github.com/YashDayma55)
- Built as part of M.S. Computer Science at George Mason University

---

## License

MIT License — feel free to use, modify, and distribute.
