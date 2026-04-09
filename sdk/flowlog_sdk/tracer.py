import uuid
import threading

# threading.local() stores data separately for each thread
# So if 100 requests come in simultaneously, each has its OWN trace_id
_local = threading.local()

def generate_trace_id():
    """Generate a unique trace ID for each request"""
    return str(uuid.uuid4())

def get_current_trace_id():
    """Get the trace ID for the current request"""
    return getattr(_local, 'trace_id', None)

def set_current_trace_id(trace_id):
    """Set the trace ID for the current request"""
    _local.trace_id = trace_id

def clear_trace_id():
    """Clear trace ID after request is done"""
    _local.trace_id = None

def get_span_order():
    """Track which function call number we're on (1st, 2nd, 3rd...)"""
    if not hasattr(_local, 'span_order'):
        _local.span_order = 0
    _local.span_order += 1
    return _local.span_order

def reset_span_order():
    """Reset span order after request is done"""
    _local.span_order = 0