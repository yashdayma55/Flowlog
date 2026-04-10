from locust import HttpUser, task, between
import random
import uuid

class FlowLogUser(HttpUser):
    # Each user waits 0.1 to 0.5 seconds between requests
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Called when a user starts — register and get API key"""
        response = self.client.post(
            "/register",
            json={"name": f"loadtest-app-{random.randint(1,100)}"}
        )
        if response.status_code == 200:
            self.api_key = response.json()["api_key"]
        else:
            self.api_key = None

    @task(3)
    def ingest_success_span(self):
        """Simulate a successful function call — weighted 3x"""
        if not self.api_key:
            return

        self.client.post(
            "/ingest/span",
            json={
                "trace_id": str(uuid.uuid4()),
                "function_name": random.choice([
                    "fetch_deals", "parse_deals",
                    "save_to_db", "auth_middleware",
                    "get_user", "send_notification"
                ]),
                "file_name": random.choice([
                    "scraper.py", "parser.py",
                    "database.py", "auth.py"
                ]),
                "line_number": random.randint(1, 300),
                "duration_ms": random.randint(5, 500),
                "status": "SUCCESS",
                "span_order": 1
            },
            headers={"X-API-Key": self.api_key}
        )

    @task(1)
    def ingest_failed_span(self):
        """Simulate a failed function call — weighted 1x"""
        if not self.api_key:
            return

        self.client.post(
            "/ingest/span",
            json={
                "trace_id": str(uuid.uuid4()),
                "function_name": "save_to_db",
                "file_name": "database.py",
                "line_number": 201,
                "duration_ms": random.randint(1000, 9000),
                "status": "FAILED",
                "span_order": 1,
                "error": {
                    "error_type": "ConnectionTimeout",
                    "error_message": "Could not connect to PostgreSQL",
                    "stack_trace": "line 201 in save_to_db"
                }
            },
            headers={"X-API-Key": self.api_key}
        )


class QueryUser(HttpUser):
    """Simulates users querying the dashboard"""
    wait_time = between(0.5, 2)
    # Point this user at Query API port
    host = "http://localhost:8001"

    @task(2)
    def get_traces(self):
        self.client.get("/traces?hours=24&limit=50")

    @task(1)
    def get_trace_detail(self):
        # Get a random trace
        response = self.client.get("/traces?limit=10")
        if response.status_code == 200:
            traces = response.json().get("traces", [])
            if traces:
                trace_id = random.choice(traces)["trace_id"]
                self.client.get(f"/traces/{trace_id}")