from datetime import datetime, timezone
import uuid

from api.db import query_couchdb, update_couchdb_doc

AGENT_CONFIGS_DB = "agent_configs"
LEGACY_MIGRATION_VERSION = 1


def extract_userspace(doc: dict) -> str | None:
    return doc.get("userspace") or doc.get("namespace")


def _default_userspace_for_legacy_user_id(user_id: str) -> str:
    try:
        return str(uuid.UUID(user_id))
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"moirai-userspace:{user_id}"))


def migrate_legacy_agent_configs() -> dict:
    docs = query_couchdb(AGENT_CONFIGS_DB, selector={})
    migrated = 0
    skipped = 0

    for doc in docs:
        if not isinstance(doc, dict):
            skipped += 1
            continue

        userspace = extract_userspace(doc)
        owner_user_id = doc.get("owner_user_id")
        legacy_user_id = doc.get("user_id")

        if userspace and owner_user_id:
            skipped += 1
            continue

        if not legacy_user_id:
            skipped += 1
            continue

        if not userspace:
            doc["userspace"] = _default_userspace_for_legacy_user_id(legacy_user_id)
        if not owner_user_id:
            doc["owner_user_id"] = legacy_user_id

        doc["migration_version"] = LEGACY_MIGRATION_VERSION
        doc["migrated_at"] = datetime.now(timezone.utc).isoformat()

        if update_couchdb_doc(AGENT_CONFIGS_DB, doc["_id"], doc):
            migrated += 1

    return {"status": "success", "migrated": migrated, "skipped": skipped}
