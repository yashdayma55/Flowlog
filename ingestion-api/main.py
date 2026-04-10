from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from kafka import KafkaProducer
import json
import os
import uuid
from models import SpanRequest, AppRegisterRequest
from database import get_db, App, engine, Base
from dotenv import load_dotenv

load_dotenv()

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FlowLog Ingestion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Kafka producer
producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_URL", "localhost:9092"),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "ingestion-api"}

@app.post("/register")
def register_app(
    request: AppRegisterRequest,
    db: Session = Depends(get_db)
):
    """Register a new app and get an API key — stored in PostgreSQL"""

    # Check if app already exists
    existing = db.query(App).filter(App.name == request.name).first()
    if existing:
        return {
            "app_name": existing.name,
            "api_key": existing.api_key,
            "message": "App already registered — here is your existing API key"
        }

    # Create new app with UUID api key
    new_app = App(
        id=uuid.uuid4(),
        name=request.name,
        api_key=str(uuid.uuid4())
    )
    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    return {
        "app_name": new_app.name,
        "api_key": new_app.api_key,
        "message": "App registered successfully — save this API key"
    }

@app.post("/ingest/span")
def ingest_span(
    span: SpanRequest,
    x_api_key: str = Header(...),
    db: Session = Depends(get_db)
):
    """Receive a span from SDK and push to Kafka"""

    # Validate API key against PostgreSQL
    app_record = db.query(App).filter(
        App.api_key == x_api_key
    ).first()

    if not app_record:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Build Kafka message
    message = {
        "app_name": app_record.name,
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

    # Push to Kafka
    producer.send("raw-logs", value=message)
    producer.flush()

    return {"status": "accepted", "trace_id": span.trace_id}

@app.get("/apps")
def list_apps(db: Session = Depends(get_db)):
    """List all registered apps — useful for debugging"""
    apps = db.query(App).all()
    return {
        "total": len(apps),
        "apps": [
            {
                "name": a.name,
                "api_key": a.api_key,
                "created_at": a.created_at
            }
            for a in apps
        ]
    }