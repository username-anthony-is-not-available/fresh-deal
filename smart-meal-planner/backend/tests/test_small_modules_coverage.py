"""Coverage tests for small backend modules left below 80%:
MockScraperAgent, both ProxyManager copies, security, db and main.
"""
import importlib
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from jose import jwt
from sqlmodel import Session, SQLModel, create_engine, select

from app.agents.mock_scraper import MockScraperAgent
from app.core.config import settings
from app.core import db as db_module
from app.core.security import (
    ALGORITHM,
    create_access_token,
    get_current_active_user,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.models.all_models import Deal, Product, Recipe, Store, User
import app.main as main_module


# ---------------------------------------------------------------------------
# MockScraperAgent
# ---------------------------------------------------------------------------

@pytest.fixture(name="sync_session")
def sync_session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_seed_recipes_from_bundled_file(sync_session):
    agent = MockScraperAgent(sync_session)
    count = agent.seed_recipes()
    assert count == 515
    assert sync_session.exec(select(Recipe)).first() is not None
    # Second call: recipes already exist, nothing to do.
    assert agent.seed_recipes() == 0


def test_seed_recipes_missing_file(monkeypatch, sync_session):
    monkeypatch.setattr("os.path.exists", lambda _path: False)
    assert MockScraperAgent(sync_session).seed_recipes() == 0


class _FakeRecipesFile(io.StringIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_seed_recipes_string_ingredients(monkeypatch, sync_session):
    data = [
        {
            "name": "String Ing Recipe",
            "ingredients": ["plain salt", {"item": "", "quantity": 1, "unit": "tsp"}],
            "instructions": ["mix"],
        }
    ]
    monkeypatch.setattr(
        "builtins.open",
        lambda *args, **kwargs: _FakeRecipesFile(json.dumps(data)),
    )
    assert MockScraperAgent(sync_session).seed_recipes() == 1
    ingredients = sync_session.exec(select(Recipe)).first()
    assert ingredients is not None


def test_generate_deals_seeds_stores_products_and_deals(sync_session):
    agent = MockScraperAgent(sync_session)
    assert agent.generate_deals() == 50
    assert len(sync_session.exec(select(Store)).all()) == 5
    assert len(sync_session.exec(select(Product)).all()) == 8
    assert len(sync_session.exec(select(Deal)).all()) == 50
    # Second run: stores/products already exist, deals are generated again.
    assert agent.generate_deals() == 50
    assert len(sync_session.exec(select(Deal)).all()) == 100


# ---------------------------------------------------------------------------
# app/core/proxy_manager.py
# ---------------------------------------------------------------------------

import app.core.proxy_manager as app_proxy_manager


def _app_pm(**kwargs):
    monkeypatch = kwargs.pop("monkeypatch")
    monkeypatch.setattr(app_proxy_manager.settings, "DISABLE_PROXIES_LOCAL", False)
    monkeypatch.delenv("DISABLE_PROXIES_LOCAL", raising=False)
    monkeypatch.delenv("PROXY_POOL", raising=False)
    return app_proxy_manager.ProxyManager(**kwargs)


def test_app_proxy_manager_disabled_by_default(monkeypatch):
    pm = app_proxy_manager.ProxyManager()
    assert pm.disable_proxies is True
    assert pm.get_proxy() is None


def test_app_proxy_manager_empty_pool_warns(monkeypatch):
    pm = _app_pm(monkeypatch=monkeypatch)
    assert pm.proxy_pool == []
    assert pm.get_proxy() is None


def test_app_proxy_manager_pool_rotation_and_blacklist(monkeypatch):
    pm = _app_pm(monkeypatch=monkeypatch, proxy_pool=["http://p1", "http://p2"])
    assert pm.get_proxy() in ("http://p1", "http://p2")
    pm.blacklist_proxy("http://p1")
    pm.blacklist_proxy("http://p2")
    assert pm.get_proxy() is None  # all blacklisted
    # Expired blacklist entries are cleaned up on the next get_proxy call.
    pm.blacklist["http://p1"] = 0.0
    assert pm.get_proxy() == "http://p1"
    # Blacklisting a proxy that is not in the pool is a no-op.
    pm.blacklist_proxy("http://unknown")
    assert "http://unknown" not in pm.blacklist


def test_app_proxy_manager_pool_from_env(monkeypatch):
    monkeypatch.setattr(app_proxy_manager.settings, "DISABLE_PROXIES_LOCAL", False)
    monkeypatch.delenv("DISABLE_PROXIES_LOCAL", raising=False)
    monkeypatch.setenv("PROXY_POOL", " http://a , http://b ")
    pm = app_proxy_manager.ProxyManager()
    assert pm.proxy_pool == ["http://a", "http://b"]
    assert pm.get_proxy() in ("http://a", "http://b")


# ---------------------------------------------------------------------------
# src/core/proxy_manager.py
# ---------------------------------------------------------------------------

from src.core.proxy_manager import ProxyManager as SrcProxyManager, USER_AGENTS


def test_src_proxy_manager(monkeypatch):
    monkeypatch.delenv("PROXY_POOL", raising=False)
    pm = SrcProxyManager()
    assert pm.get_proxy() is None
    assert pm.get_user_agent() in USER_AGENTS
    pm = SrcProxyManager(proxy_pool=["http://p1", "http://p2"])
    assert pm.get_proxy() in ("http://p1", "http://p2")
    pm.blacklist_proxy("http://p1")
    pm.blacklist_proxy("http://p2")
    assert pm.get_proxy() is None
    pm.blacklist["http://p1"] = 0.0
    assert pm.get_proxy() == "http://p1"
    pm.blacklist_proxy("http://unknown")
    assert "http://unknown" not in pm.blacklist


def test_src_proxy_manager_pool_from_env(monkeypatch):
    monkeypatch.setenv("PROXY_POOL", "http://a,http://b")
    pm = SrcProxyManager()
    assert pm.proxy_pool == ["http://a", "http://b"]


# ---------------------------------------------------------------------------
# security
# ---------------------------------------------------------------------------

class _FakeSession:
    def __init__(self, user):
        self._user = user

    def get(self, _model, _user_id):
        return self._user


def test_create_access_token_with_and_without_delta():
    from datetime import timedelta

    token = create_access_token("42", expires_delta=timedelta(minutes=5))
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "42"
    token2 = create_access_token("7")
    payload2 = jwt.decode(token2, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload2["sub"] == "7"


def test_password_hash_and_verify():
    hashed = get_password_hash("correct horse")
    assert verify_password("correct horse", hashed) is True
    assert verify_password("wrong horse", hashed) is False


def test_get_current_user_happy_path():
    user = User(email="a@b.c", hashed_password="x", is_active=True)
    token = create_access_token("123")
    assert get_current_user(token=token, session=_FakeSession(user)) is user


def test_get_current_user_rejects_bad_tokens():
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(token="not-a-jwt", session=_FakeSession(None))
    assert excinfo.value.status_code == 401
    # Valid JWT but no subject.
    token = jwt.encode({"exp": 9999999999}, settings.SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(token=token, session=_FakeSession(None))
    assert excinfo.value.status_code == 401
    # Valid subject but no such user.
    token = create_access_token("999")
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(token=token, session=_FakeSession(None))
    assert excinfo.value.status_code == 401


def test_get_current_active_user():
    active = User(email="a@b.c", hashed_password="x", is_active=True)
    assert get_current_active_user(current_user=active) is active
    inactive = User(email="b@c.d", hashed_password="x", is_active=False)
    with pytest.raises(HTTPException) as excinfo:
        get_current_active_user(current_user=inactive)
    assert excinfo.value.status_code == 400


# ---------------------------------------------------------------------------
# db
# ---------------------------------------------------------------------------

def test_get_session_uses_context_manager(monkeypatch):
    sentinel = object()

    class _FakeSessionCtx:
        def __init__(self, _engine):
            pass

        def __enter__(self):
            return sentinel

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(db_module, "Session", _FakeSessionCtx)
    assert list(db_module.get_session()) == [sentinel]


@pytest.mark.asyncio
async def test_get_async_session(monkeypatch):
    sentinel = object()

    class _FakeConn:
        async def run_sync(self, _fn):
            return None

    class _FakeBegin:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, *exc):
            return False

    class _FakeAsyncEngine:
        def begin(self):
            return _FakeBegin()

    class _FakeAsyncSessionCtx:
        async def __aenter__(self):
            return sentinel

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(db_module, "async_engine", _FakeAsyncEngine())
    monkeypatch.setattr(
        db_module, "sessionmaker", lambda *a, **k: lambda: _FakeAsyncSessionCtx()
    )
    assert [s async for s in db_module.get_async_session()] == [sentinel]


def test_db_module_uri_branches(monkeypatch):
    orig_property = type(settings).__dict__["SQLALCHEMY_DATABASE_URI"]
    try:
        # postgres:// scheme is normalized to postgresql://.
        monkeypatch.setattr(
            type(settings),
            "SQLALCHEMY_DATABASE_URI",
            property(lambda self: "postgres://u:p@localhost:5432/testdb"),
        )
        importlib.reload(db_module)
        assert db_module.connection_string.startswith("postgresql://")
        # sqlite URI takes the check_same_thread and sqlite+aiosqlite paths.
        monkeypatch.setattr(
            type(settings),
            "SQLALCHEMY_DATABASE_URI",
            property(lambda self: "sqlite:///./test.db"),
        )
        importlib.reload(db_module)
        assert db_module.connect_args == {"check_same_thread": False}
        assert db_module.async_connection_string.startswith("sqlite+aiosqlite://")
    finally:
        monkeypatch.setattr(
            type(settings), "SQLALCHEMY_DATABASE_URI", orig_property
        )
        importlib.reload(db_module)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def test_init_db_creates_tables(monkeypatch):
    create_all = MagicMock()
    monkeypatch.setattr(
        db_module, "SQLModel", SimpleNamespace(metadata=SimpleNamespace(create_all=create_all))
    )
    db_module.init_db()
    create_all.assert_called_once_with(db_module.engine)


@pytest.mark.asyncio
async def test_lifespan_schedules_jobs(monkeypatch):
    monkeypatch.setattr(main_module, "setup_logging", MagicMock())
    monkeypatch.setattr(main_module, "init_db", MagicMock())
    monkeypatch.setattr(main_module, "sentry_sdk", MagicMock())
    scheduler = MagicMock()
    monkeypatch.setattr(main_module, "scheduler", scheduler)
    # main.py builds its own Settings() instance; patch that one.
    monkeypatch.setattr(
        main_module.settings, "SENTRY_DSN", "https://x@y.ingest.sentry.io/1"
    )
    monkeypatch.setenv("REFRESH_CRON_SCHEDULE", "30 6 * * *")
    async with main_module.lifespan(main_module.app):
        pass
    assert main_module.sentry_sdk.init.called
    assert scheduler.add_job.call_count == 4
    assert scheduler.start.called
    assert scheduler.shutdown.called


@pytest.mark.asyncio
async def test_lifespan_invalid_cron_falls_back(monkeypatch):
    monkeypatch.setattr(main_module, "setup_logging", MagicMock())
    monkeypatch.setattr(main_module, "init_db", MagicMock())
    monkeypatch.setattr(main_module, "sentry_sdk", MagicMock())
    scheduler = MagicMock()
    monkeypatch.setattr(main_module, "scheduler", scheduler)
    monkeypatch.setattr(main_module.settings, "SENTRY_DSN", None)
    monkeypatch.setenv("REFRESH_CRON_SCHEDULE", "not-a-cron")
    async with main_module.lifespan(main_module.app):
        pass
    assert not main_module.sentry_sdk.init.called
    fallback = [
        c for c in scheduler.add_job.call_args_list if c.kwargs.get("hour") == 6
    ]
    assert fallback


@pytest.mark.parametrize(
    "detail,expected",
    [
        ("Rate limit exceeded: 5 per 1 second", "1"),
        ("Rate limit exceeded: 10 per 2 minute", "120"),
        ("Rate limit exceeded: 3 per 1 hour", "3600"),
        ("Rate limit exceeded: 1 per 1 day", "86400"),
        ("Rate limit exceeded", "60"),
        ("", "60"),
    ],
)
def test_rate_limit_exceeded_handler(detail, expected):
    exc = SimpleNamespace(detail=detail)
    response = main_module._rate_limit_exceeded_handler(None, exc)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == expected
