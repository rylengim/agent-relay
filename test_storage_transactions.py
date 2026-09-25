"""Storage regressions shared by SQLite and the PostgreSQL test database."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

os.environ.setdefault("RELAY_DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:////tmp/agent-relay-test.db"))

import pytest
from sqlalchemy import select

import database
import storage
from database import Attempt, Base, Task, as_db_time, db_session, engine, utcnow
from errors import RelayError


@pytest.fixture(autouse=True)
def clean_storage():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def make_task():
    sender = storage.register_agent("sender", None)["agent_id"]
    recipient = storage.register_agent("recipient", None)["agent_id"]
    task = storage.create_task(sender, recipient, "hello", None)
    return sender, recipient, task["task_id"]


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_postgres_urls_use_installed_psycopg_driver(monkeypatch, scheme):
    monkeypatch.setenv("RELAY_DATABASE_URL", f"{scheme}://relay:password@localhost/relay")
    assert database._database_url() == "postgresql+psycopg://relay:password@localhost/relay"


def test_concurrent_idempotent_creates_return_one_task():
    sender, recipient, _ = make_task()
    barrier = Barrier(8)

    def send(_):
        barrier.wait(timeout=10)
        return storage.create_task(sender, recipient, "same payload", "concurrent-key")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(send, range(8)))

    assert len({result["task_id"] for result in results}) == 1
    with db_session() as db:
        tasks = list(db.scalars(select(Task).where(Task.idempotency_key == "concurrent-key")))
        assert len(tasks) == 1


def test_concurrent_api_startup_creates_schema_once():
    Base.metadata.drop_all(engine)
    barrier = Barrier(4)

    def initialize(_):
        barrier.wait(timeout=10)
        database.init_db()

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(initialize, range(4)))

    _, recipient, task_id = make_task()
    assert storage.claim_one(recipient, "startup-worker")["task_id"] == task_id


def test_concurrent_conflicting_creates_return_one_conflict():
    sender, recipient, _ = make_task()
    barrier = Barrier(2)

    def send(value):
        barrier.wait(timeout=10)
        try:
            return storage.create_task(sender, recipient, value, "conflicting-key")
        except RelayError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, ["first payload", "second payload"]))

    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count("idempotency_conflict") == 1


def test_simultaneous_terminal_submissions_preserve_first_result():
    _, recipient, task_id = make_task()
    claim = storage.claim_one(recipient, "worker")
    barrier = Barrier(2)

    def finish(value):
        barrier.wait(timeout=10)
        try:
            return storage.commit_terminal(
                task_id, recipient, claim["claim_token"], action="complete", value=value
            )
        except RelayError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(finish, ["first output", "second output"]))

    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count("conflicting_terminal") == 1
    accepted = "first output" if isinstance(results[0], dict) else "second output"
    assert storage.task_for_participant(task_id, recipient).output == accepted
    assert storage.commit_terminal(
        task_id, recipient, claim["claim_token"], action="complete", value=accepted
    )["status"] == "completed"


def test_heartbeat_and_terminal_race_cannot_revive_finished_attempt():
    _, recipient, task_id = make_task()
    claim = storage.claim_one(recipient, "worker")
    barrier = Barrier(2)

    def renew():
        barrier.wait(timeout=10)
        try:
            return storage.heartbeat(task_id, recipient, claim["claim_token"])
        except RelayError as error:
            return error.code

    def finish():
        barrier.wait(timeout=10)
        return storage.commit_terminal(
            task_id, recipient, claim["claim_token"], action="complete", value="HELLO"
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        heartbeat = pool.submit(renew)
        terminal = pool.submit(finish)
        assert terminal.result(timeout=10)["status"] == "completed"
        heartbeat.result(timeout=10)

    with pytest.raises(RelayError) as stale:
        storage.heartbeat(task_id, recipient, claim["claim_token"])
    assert stale.value.code == "stale_claim"
    attempts = storage.attempts_for_participant(task_id, recipient)
    assert [attempt.outcome for attempt in attempts] == ["completed"]


def test_concurrent_recovery_expires_an_attempt_only_once():
    _, recipient, task_id = make_task()
    claim = storage.claim_one(recipient, "old-worker")
    with db_session() as db:
        attempt = db.scalar(select(Attempt).where(Attempt.task_id == task_id))
        attempt.lease_expires_at = as_db_time(utcnow() - timedelta(seconds=1))
    barrier = Barrier(4)

    def recover(_):
        barrier.wait(timeout=10)
        return storage.recover_expired()

    with ThreadPoolExecutor(max_workers=4) as pool:
        recovered = list(pool.map(recover, range(4)))

    assert sum(recovered) == 1
    next_claim = storage.claim_one(recipient, "new-worker")
    assert next_claim["attempt"] == 2
    assert next_claim["claim_token"] != claim["claim_token"]
    with pytest.raises(RelayError) as stale:
        storage.commit_terminal(task_id, recipient, claim["claim_token"], action="complete", value="late")
    assert stale.value.code == "stale_claim"


@pytest.mark.parametrize("action", ["heartbeat", "complete"])
def test_recovery_and_active_worker_agree_on_lease_owner(monkeypatch, action):
    _, recipient, task_id = make_task()
    start = utcnow()
    claim = storage.claim_one(recipient, "worker")
    # Model an in-flight worker request spanning the lease deadline. Depending
    # on which transaction wins, its renewal/result succeeds OR recovery does.
    # A successful renewal/result and requeue together are never acceptable.
    with db_session() as db:
        attempt = db.scalar(select(Attempt).where(Attempt.task_id == task_id))
        attempt.lease_expires_at = as_db_time(start + timedelta(seconds=60))
    monkeypatch.setattr(storage, "utcnow", lambda: start + timedelta(seconds=40))
    monkeypatch.setattr(database, "utcnow", lambda: start + timedelta(seconds=70))
    barrier = Barrier(2)

    def worker_request():
        barrier.wait(timeout=10)
        try:
            if action == "heartbeat":
                storage.heartbeat(task_id, recipient, claim["claim_token"])
            else:
                storage.commit_terminal(task_id, recipient, claim["claim_token"], action="complete", value="HELLO")
            return "accepted"
        except RelayError as error:
            return error.code

    def recover():
        barrier.wait(timeout=10)
        return storage.recover_expired()

    with ThreadPoolExecutor(max_workers=2) as pool:
        worker = pool.submit(worker_request)
        recovery = pool.submit(recover)
        outcome = worker.result(timeout=10)
        recovered = recovery.result(timeout=10)

    assert (outcome, recovered) in {("accepted", 0), ("stale_claim", 1)}
    task = storage.task_for_participant(task_id, recipient)
    attempt = storage.attempts_for_participant(task_id, recipient)[0]
    if outcome == "stale_claim":
        assert task.status == "queued"
        assert attempt.outcome == "expired"
    else:
        expected = "processing" if action == "heartbeat" else "completed"
        assert task.status == attempt.outcome == expected
