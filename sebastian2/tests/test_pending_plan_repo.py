"""Tests for PendingPlanRepository."""
import json
import sqlite3
from datetime import datetime, timedelta
import pytest
from tests.test_item_list_module import MySQLCompatibleConnection
from db.pending_plan_repo import PendingPlanRepository

_SCHEMA = '''
    CREATE TABLE pending_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL UNIQUE,
        original_message TEXT NOT NULL,
        messages_json TEXT NOT NULL,
        question TEXT NOT NULL,
        missing_field TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME NOT NULL
    )
'''


@pytest.fixture
def db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    yield MySQLCompatibleConnection(conn)


def _save(repo, user_id="u1", msg="¿paraguas?", messages=None, question="¿ciudad?", field="city"):
    messages_json = json.dumps(messages or [{"role": "user", "content": msg}])
    repo.save(user_id, msg, messages_json, question, field)


def test_save_and_get_active(db):
    repo = PendingPlanRepository(db)
    _save(repo)
    plan = repo.get_active("u1")
    assert plan is not None
    assert plan["question"] == "¿ciudad?"
    assert plan["missing_field"] == "city"
    assert json.loads(plan["messages_json"]) == [{"role": "user", "content": "¿paraguas?"}]


def test_get_active_returns_none_when_no_plan(db):
    repo = PendingPlanRepository(db)
    assert repo.get_active("u1") is None


def test_get_active_ignores_expired(db):
    repo = PendingPlanRepository(db)
    past = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    db._conn.execute(
        "INSERT INTO pending_plans (user_id, original_message, messages_json, question, expires_at)"
        " VALUES (?,?,?,?,?)",
        ("u1", "test", "[]", "?", past)
    )
    db._conn.commit()
    assert repo.get_active("u1") is None


def test_save_overwrites_existing_plan(db):
    repo = PendingPlanRepository(db)
    _save(repo, question="¿ciudad?")
    _save(repo, question="¿fecha?", field="date")
    plan = repo.get_active("u1")
    assert plan["question"] == "¿fecha?"
    assert plan["missing_field"] == "date"


def test_delete_returns_true_when_deleted(db):
    repo = PendingPlanRepository(db)
    _save(repo)
    assert repo.delete("u1") is True
    assert repo.get_active("u1") is None


def test_delete_returns_false_when_no_plan(db):
    repo = PendingPlanRepository(db)
    assert repo.delete("u1") is False


def test_delete_all(db):
    repo = PendingPlanRepository(db)
    _save(repo, user_id="u1")
    _save(repo, user_id="u2")
    count = repo.delete_all()
    assert count == 2
    assert repo.get_active("u1") is None
    assert repo.get_active("u2") is None
