def approval_allowed(payload):
    return int(payload["summary"].get("REJECT", 0)) == 0
