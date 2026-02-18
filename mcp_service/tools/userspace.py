from typing import Any


def extract_userspace(doc: dict[str, Any]) -> str | None:
    return doc.get("userspace") or doc.get("namespace")


def with_userspace(doc: dict[str, Any], userspace: str) -> dict[str, Any]:
    doc["userspace"] = userspace
    return doc


def build_userspace_selector(userspace: str) -> dict[str, Any]:
    return {"$or": [{"userspace": userspace}, {"namespace": userspace}]}
