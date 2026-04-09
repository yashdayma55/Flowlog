from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class ErrorData(BaseModel):
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None

class SpanRequest(BaseModel):
    trace_id: str
    function_name: str
    file_name: Optional[str] = None
    line_number: Optional[int] = None
    duration_ms: Optional[int] = None
    status: str = "SUCCESS"
    span_order: Optional[int] = None
    error: Optional[ErrorData] = None
    metadata: Optional[Dict[str, Any]] = None

class AppRegisterRequest(BaseModel):
    name: str