from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
from database import get_db
from models import Trace, Span, App, Error
import uuid

app = FastAPI(title="FlowLog Query API")

@app.get("/health")
def health():
    return {"status": "ok", "service": "query-api"}

@app.get("/traces")
def get_traces(
    app_name: Optional[str] = None,
    status: Optional[str] = None,
    hours: Optional[int] = 24,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List all traces with optional filters.
    
    Examples:
    GET /traces                          → last 24h traces
    GET /traces?app_name=dealhunter      → only dealhunter traces
    GET /traces?status=FAILED            → only failed traces
    GET /traces?hours=1                  → last 1 hour only
    """
    query = db.query(Trace)

    # Filter by time
    since = datetime.utcnow() - timedelta(hours=hours)
    query = query.filter(Trace.created_at >= since)

    # Filter by app name
    if app_name:
        app = db.query(App).filter(App.name == app_name).first()
        if app:
            query = query.filter(Trace.app_id == app.id)

    # Filter by status
    if status:
        query = query.filter(Trace.status == status.upper())

    traces = query.order_by(Trace.created_at.desc()).limit(limit).all()

    return {
        "total": len(traces),
        "traces": [
            {
                "trace_id": t.trace_id,
                "status": t.status,
                "endpoint": t.endpoint,
                "total_duration_ms": t.total_duration_ms,
                "created_at": t.created_at,
                "span_count": len(t.spans)
            }
            for t in traces
        ]
    }

@app.get("/traces/{trace_id}")
def get_trace_detail(
    trace_id: str,
    db: Session = Depends(get_db)
):
    """
    Get full trace with all spans in order.
    This reconstructs the entire function call flow.
    
    Example:
    GET /traces/test-trace-004
    """
    trace = db.query(Trace).filter(
        Trace.trace_id == trace_id
    ).first()

    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    # Build the full flow
    spans_data = []
    for span in trace.spans:
        span_dict = {
            "id": str(span.id),
            "function_name": span.function_name,
            "file_name": span.file_name,
            "line_number": span.line_number,
            "duration_ms": span.duration_ms,
            "status": span.status,
            "span_order": span.span_order,
            "metadata": span.extra_data,
            "created_at": span.created_at,
            "error": None
        }

        # Include error details if span failed
        if span.errors:
            error = span.errors[0]
            span_dict["error"] = {
                "error_type": error.error_type,
                "error_message": error.error_message,
                "stack_trace": error.stack_trace
            }

        spans_data.append(span_dict)

    return {
        "trace_id": trace.trace_id,
        "status": trace.status,
        "endpoint": trace.endpoint,
        "total_duration_ms": trace.total_duration_ms,
        "created_at": trace.created_at,
        "flow": spans_data  # full ordered function call chain
    }

@app.get("/spans")
def get_spans(
    function_name: Optional[str] = None,
    file_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Search spans with filters.
    
    Examples:
    GET /spans?function_name=fetch_deals  → all calls to fetch_deals
    GET /spans?file_name=scraper.py       → all spans from scraper.py
    GET /spans?status=FAILED              → all failed function calls
    """
    query = db.query(Span)

    if function_name:
        query = query.filter(
            Span.function_name.ilike(f"%{function_name}%")
        )
    if file_name:
        query = query.filter(
            Span.file_name.ilike(f"%{file_name}%")
        )
    if status:
        query = query.filter(Span.status == status.upper())

    spans = query.order_by(Span.created_at.desc()).limit(limit).all()

    return {
        "total": len(spans),
        "spans": [
            {
                "id": str(s.id),
                "trace_id": s.trace_id,
                "function_name": s.function_name,
                "file_name": s.file_name,
                "line_number": s.line_number,
                "duration_ms": s.duration_ms,
                "status": s.status,
                "span_order": s.span_order,
                "created_at": s.created_at
            }
            for s in spans
        ]
    }