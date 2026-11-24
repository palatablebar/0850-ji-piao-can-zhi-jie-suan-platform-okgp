def all_checks(checks):
    return all(item["ok"] for item in checks)
