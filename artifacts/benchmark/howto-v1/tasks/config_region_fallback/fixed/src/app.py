def resolve_region(config):
    region = config.get("region", "us-west-1")
    if isinstance(region, str) and not region.strip():
        return "us-west-1"
    return region
