
CREATE TABLE IF NOT EXISTS apps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    api_key VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Traces table: one row per request
CREATE TABLE IF NOT EXISTS traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(100) NOT NULL UNIQUE,
    app_id UUID NOT NULL REFERENCES apps(id),
    endpoint VARCHAR(255),
    total_duration_ms INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Spans table: one row per function call
CREATE TABLE IF NOT EXISTS spans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(100) NOT NULL REFERENCES traces(trace_id),
    function_name VARCHAR(255) NOT NULL,
    file_name VARCHAR(255),
    line_number INTEGER,
    duration_ms INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    span_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Errors table: error details when a span fails
CREATE TABLE IF NOT EXISTS errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    span_id UUID NOT NULL REFERENCES spans(id),
    error_type VARCHAR(255),
    error_message TEXT,
    stack_trace TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast querying
CREATE INDEX IF NOT EXISTS idx_traces_app_id ON traces(app_id);
CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at);
CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_errors_span_id ON errors(span_id);

-- Spans table: one row per function call
CREATE TABLE IF NOT EXISTS spans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(100) NOT NULL REFERENCES traces(trace_id),
    function_name VARCHAR(255) NOT NULL,
    file_name VARCHAR(255),
    line_number INTEGER,
    duration_ms INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    span_order INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);