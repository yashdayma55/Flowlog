from flowlog_sdk import trace, init

# Initialize SDK (pointing to our ingestion API later)
init(api_url="http://localhost:8000", api_key="test-key-123")

@trace
def fetch_deals():
    print("Fetching deals...")
    return ["deal1", "deal2"]

@trace
def parse_deals(deals):
    print(f"Parsing {len(deals)} deals...")
    return deals

@trace
def save_to_db(deals):
    print("Saving to database...")
    # Simulate a failure
    raise Exception("Connection timeout")

# Simulate a request
try:
    deals = fetch_deals()
    parsed = parse_deals(deals)
    save_to_db(parsed)
except Exception as e:
    print(f"Request failed: {e}")