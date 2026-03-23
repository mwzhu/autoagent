def extract_items(response):
    return response.get("data", {}).get("items", [])
