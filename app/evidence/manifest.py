import hashlib
import json


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_digest(value) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"))
