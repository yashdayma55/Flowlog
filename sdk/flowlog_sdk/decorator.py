import time
import inspect
import traceback
import functools
from .tracer import (
    generate_trace_id,
    get_current_trace_id,
    set_current_trace_id,
    clear_trace_id,
    get_span_order,
    reset_span_order
)

# This will be set when developer initializes the SDK
_api_url = None
_api_key = None

def init(api_url, api_key):
    """Developer calls this once to initialize the SDK"""
    global _api_url, _api_key
    _api_url = api_url
    _api_key = api_key

def trace(func):
    """
    The @trace decorator.
    Wraps any function to automatically capture:
    - function name
    - file name  
    - line number
    - duration
    - success/failure
    - full trace flow
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import requests

        # Check if this is the first function in the request
        # If so, generate a new trace ID
        is_root = get_current_trace_id() is None
        if is_root:
            trace_id = generate_trace_id()
            set_current_trace_id(trace_id)
        else:
            trace_id = get_current_trace_id()

        # Get exact file name, function name, line number
        # inspect module lets us look at the code itself
        frame = inspect.getframeinfo(inspect.currentframe().f_back)
        source = inspect.getsourcefile(func)
        lines, start_line = inspect.getsourcelines(func)

        span_order = get_span_order()
        start_time = time.time()
        status = "SUCCESS"
        error_data = None
        result = None

        try:
            # Actually call the original function
            result = func(*args, **kwargs)
        except Exception as e:
            # Something went wrong — capture the error
            status = "FAILED"
            error_data = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": traceback.format_exc()
            }
            raise
        finally:
            # This runs whether success or failure
            duration_ms = int((time.time() - start_time) * 1000)

            # Build the span data
            span = {
                "trace_id": trace_id,
                "function_name": func.__name__,
                "file_name": source.split("\\")[-1] if source else "unknown",
                "line_number": start_line,
                "duration_ms": duration_ms,
                "status": status,
                "span_order": span_order,
                "error": error_data
            }

            # Send to FlowLog ingestion API
            if _api_url and _api_key:
                try:
                    requests.post(
                        f"{_api_url}/ingest/span",
                        json=span,
                        headers={"X-API-Key": _api_key},
                        timeout=2  # don't slow down the app
                    )
                except Exception:
                    pass  # never let logging break the app

            # If this was the root function, clean up
            if is_root:
                clear_trace_id()
                reset_span_order()

        return result
    return wrapper