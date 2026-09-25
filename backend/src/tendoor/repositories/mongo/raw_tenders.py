"""Колекція tenders_raw: документи API Prozorro без зміни структури."""

import hashlib
import json
from datetime import UTC, datetime

from pymongo import ASCENDING, UpdateOne
from pymongo.asynchronous.database import AsyncDatabase


def doc_hash(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class MongoRawTenderRepository:
    def __init__(self, db: AsyncDatabase) -> None:
        self._col = db["tenders_raw"]

    async def ensure_indexes(self) -> None:
        await self._col.create_index([("normalizedAt", ASCENDING)])
        await self._col.create_index([("dateModified", ASCENDING)])
        await self._col.create_index([("data.items.classification.id", ASCENDING)])

    async def upsert_many(self, docs: list[dict]) -> int:
        if not docs:
            return 0
        hashes = {d["id"]: doc_hash(d) for d in docs}
        known = {
            r["_id"]: r.get("hash") async for r in self._col.find({"_id": {"$in": list(hashes)}}, {"hash": 1})
        }
        now = datetime.now(UTC)
        ops = [
            UpdateOne(
                {"_id": d["id"]},
                {
                    "$set": {
                        "tenderID": d.get("tenderID"),
                        "dateModified": d.get("dateModified"),
                        "fetchedAt": now,
                        "hash": hashes[d["id"]],
                        "normalizedAt": None,
                        "data": d,
                    }
                },
                upsert=True,
            )
            for d in docs
            if known.get(d["id"]) != hashes[d["id"]]
        ]
        if ops:
            await self._col.bulk_write(ops, ordered=False)
        return len(ops)

    async def pending_normalization(self, limit: int) -> list[dict]:
        cursor = self._col.find({"normalizedAt": None}, {"data": 1}).limit(limit)
        return [r["data"] async for r in cursor]

    async def mark_normalized(self, ids: list[str]) -> None:
        if ids:
            await self._col.update_many({"_id": {"$in": ids}}, {"$set": {"normalizedAt": datetime.now(UTC)}})

    async def count(self) -> int:
        return await self._col.estimated_document_count()
