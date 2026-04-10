from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class App(Base):
    __tablename__ = "apps"

    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(100), nullable=False)
    api_key = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    traces = relationship("Trace", back_populates="app")

class Trace(Base):
    __tablename__ = "traces"

    id = Column(UUID(as_uuid=True), primary_key=True)
    trace_id = Column(String(100), nullable=False, unique=True)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id"))
    endpoint = Column(String(255))
    total_duration_ms = Column(Integer)
    status = Column(String(20), default="SUCCESS")
    created_at = Column(DateTime, default=datetime.utcnow)

    app = relationship("App", back_populates="traces")
    spans = relationship("Span", back_populates="trace",
                        order_by="Span.span_order")

class Span(Base):
    __tablename__ = "spans"

    id = Column(UUID(as_uuid=True), primary_key=True)
    trace_id = Column(String(100), ForeignKey("traces.trace_id"))
    function_name = Column(String(255), nullable=False)
    file_name = Column(String(255))
    line_number = Column(Integer)
    duration_ms = Column(Integer)
    status = Column(String(20), default="SUCCESS")
    span_order = Column(Integer)
    extra_data = Column("metadata", JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

    trace = relationship("Trace", back_populates="spans")
    errors = relationship("Error", back_populates="span")

class Error(Base):
    __tablename__ = "errors"

    id = Column(UUID(as_uuid=True), primary_key=True)
    span_id = Column(UUID(as_uuid=True), ForeignKey("spans.id"))
    error_type = Column(String(255))
    error_message = Column(Text)
    stack_trace = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    span = relationship("Span", back_populates="errors")