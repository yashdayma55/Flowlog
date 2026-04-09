from fastapi import FastAPI, HTTPException, Header
from kafka import KafkaProducer
import json
import os
import uuid
from models import SpanRequest, AppRegisterRequest
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="FlowLog Ingestion API")

# Kafka producer — sends messages to Kafka
producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_URL", "localhost:9092"),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# In-memory app registry for now
# Later we'll move this to PostgreSQL
app_registry = {}

@app.get("/health")
def health():
    return {"status": "ok", "service": "ingestion-api"}

@app.post("/register")
def register_app(request: AppRegisterRequest):
    """Register a new app and get an API key"""
    api_key = str(uuid.uuid4())
    app_registry[api_key] = request.name
    return {
        "app_name": request.name,
        "api_key": api_key,
        "message": "Save this API key — you'll need it in your SDK init()"
    }

@app.post("/ingest/span")
def ingest_span(
    span: SpanRequest,
    x_api_key: str = Header(...)
):
    """Receive a span from SDK and push to Kafka"""

    # Validate API key
    if x_api_key not in app_registry:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Build the message to send to Kafka
    message = {
        "app_name": app_registry[x_api_key],
        "trace_id": span.trace_id,
        "function_name": span.function_name,
        "file_name": span.file_name,
        "line_number": span.line_number,
        "duration_ms": span.duration_ms,
        "status": span.status,
        "span_order": span.span_order,
        "error": span.error.dict() if span.error else None,
        "metadata": span.metadata
    }

    # Push to Kafka topic
    producer.send("raw-logs", value=message)
    producer.flush()

    return {"status": "accepted", "trace_id": span.trace_id}