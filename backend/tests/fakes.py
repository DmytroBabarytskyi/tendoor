"""Фейкові репозиторії в пам'яті для тестів API; сервіси (auth, users, tokens) — справжні."""

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta

from tendoor.config import Settings
from tendoor.infra.security import TokenService, hash_password
from tendoor.repositories.base import AuditEntry, SyncJobData, UserData
from tendoor.services.auth import AuthService, LoginLimiter
from tendoor.services.users import UserService

PASSWORD = "Test-password-1"


class FakeSyncJobs:
    def __init__(self) -> None:
        self.jobs: dict[int, SyncJobData] = {}

    async def create(self, date_from: date, date_to: date, cpv_prefixes, categories, created_by=None):
        job = SyncJobData(
            id=len(self.jobs) + 1,
            status="queued",
            date_from=date_from,
            date_to=date_to,
            cpv_prefixes=cpv_prefixes,
            categories=categories,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self.jobs[job.id] = job
        return job

    async def get(self, job_id: int):
        return self.jobs.get(job_id)

    async def list_recent(self, limit: int = 20):
        return sorted(self.jobs.values(), key=lambda j: -j.id)[:limit]


class FakeProcurement:
    async def stats(self) -> dict:
        return {"tenders": 3, "items": 10, "items_priced": 7}


class FakeRaw:
    async def count(self) -> int:
        return 5


class FakeUsers:
    def __init__(self) -> None:
        self.users: dict[int, UserData] = {}
        self.hashes: dict[int, str] = {}

    def add(self, email: str, role: str, active: bool = True) -> UserData:
        u = UserData(
            id=len(self.users) + 1,
            email=email,
            full_name=email.split("@")[0],
            role=role,
            is_active=active,
            token_version=0,
            created_at=datetime.now(UTC),
        )
        self.users[u.id], self.hashes[u.id] = u, hash_password(PASSWORD)
        return u

    async def get(self, user_id):
        return self.users.get(user_id)

    async def get_with_hash(self, email):
        u = next((u for u in self.users.values() if u.email == email.lower()), None)
        return (u, self.hashes[u.id]) if u else None

    async def get_hash(self, user_id):
        return self.hashes.get(user_id)

    async def list_all(self):
        return list(self.users.values())

    async def count(self):
        return len(self.users)

    async def roles(self):
        return [("admin", "Адміністратор"), ("analyst", "Аналітик"), ("auditor", "Аудитор")]

    async def create(self, actor_id, email, full_name, role, password_hash):
        u = self.add(email.lower(), role)
        self.users[u.id] = replace(u, full_name=full_name)
        self.hashes[u.id] = password_hash
        return self.users[u.id]

    async def update(self, actor_id, user_id, **fields):
        u = self.users.get(user_id)
        if u is None:
            return None
        if "password_hash" in fields:
            self.hashes[user_id] = fields.pop("password_hash")
            u = replace(u, token_version=u.token_version + 1)
        if fields.get("is_active") is False:
            u = replace(u, token_version=u.token_version + 1)
        self.users[user_id] = replace(u, **fields)
        return self.users[user_id]

    async def bump_token_version(self, user_id):
        u = self.users[user_id]
        self.users[user_id] = replace(u, token_version=u.token_version + 1)

    async def touch_login(self, user_id):
        self.users[user_id] = replace(self.users[user_id], last_login_at=datetime.now(UTC))


class FakeAudit:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    async def log(self, user_id, action, entity, entity_key=None, payload=None, ip=None):
        self.entries.append(
            AuditEntry(
                len(self.entries) + 1,
                user_id,
                None,
                action,
                entity,
                entity_key,
                payload,
                ip,
                datetime.now(UTC),
            )
        )

    async def search(self, entity, user_id, action, limit, offset):
        items = [
            e
            for e in reversed(self.entries)
            if (not entity or e.entity == entity)
            and (not action or e.action == action)
            and (not user_id or e.user_id == user_id)
        ]
        return items[offset : offset + limit], len(items)


class FakeConfig:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.items = {
            "detection.defaults": {
                "key": "detection.defaults",
                "value": {"k_max": 20},
                "description": "тест",
                "updated_by": None,
                "updated_at": now,
            }
        }

    async def list_all(self):
        return list(self.items.values())

    async def get(self, key):
        return self.items.get(key)

    async def set(self, actor_id, key, value):
        if key not in self.items:
            return None
        self.items[key] = {**self.items[key], "value": value, "updated_by": actor_id}
        return self.items[key]


@dataclass
class FakeContainer:
    settings: Settings = field(default_factory=Settings)
    sync_jobs: FakeSyncJobs = field(default_factory=FakeSyncJobs)
    procurement: FakeProcurement = field(default_factory=FakeProcurement)
    raw_tenders: FakeRaw = field(default_factory=FakeRaw)
    users: FakeUsers = field(default_factory=FakeUsers)
    audit: FakeAudit = field(default_factory=FakeAudit)
    config: FakeConfig = field(default_factory=FakeConfig)
    tokens: TokenService = field(
        default_factory=lambda: TokenService(
            "test-secret-test-secret-test-secret-42", timedelta(minutes=15), timedelta(days=7)
        )
    )

    def __post_init__(self) -> None:
        self.auth = AuthService(self.users, self.audit, self.tokens, LoginLimiter(5, 300))
        self.user_service = UserService(self.users)
        self.admin = self.users.add("admin@test.ua", "admin")
        self.analyst = self.users.add("analyst@test.ua", "analyst")
        self.auditor = self.users.add("auditor@test.ua", "auditor")
