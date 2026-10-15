"""Every eligibility transition invalidates snapshots, including direct SQL paths."""

from memory.shared.journal import EventJournal


def test_generation_survives_restart_and_idempotent_submit(tmp_path):
    path = tmp_path / "events.sqlite"
    journal = EventJournal(path)
    assert journal.generation("A") == 0
    journal.submit("A", "first", "digest", "user", {"text": "budget"}, "mid", True)
    submitted = journal.generation("A")
    assert submitted > 0 and journal.generation("B") == 0
    journal.submit("A", "first", "digest", "user", {"text": "budget"}, "mid", True)
    assert journal.generation("A") == submitted
    row = journal.take()
    assert journal.generation("A") > submitted
    journal.finish(row, {"status": "ready"})
    ready = journal.generation("A")
    journal.close()
    journal = EventJournal(path)
    assert journal.generation("A") == ready
    journal.close()


def test_failed_retry_withdraw_redact_and_future_sql_paths_are_covered(tmp_path):
    journal = EventJournal(tmp_path / "events.sqlite")
    journal.submit("A", "first", "digest", "user", {"text": "private"}, "mid", True)
    row = journal.take()
    previous = journal.generation("A")
    journal.fail(row, "test failure")
    assert journal.generation("A") > previous
    previous = journal.generation("A")
    journal.retry("A", "first")
    assert journal.generation("A") > previous
    previous = journal.generation("A")
    with journal.lock, journal.db:
        journal.db.execute("UPDATE events SET status='withdrawn' WHERE tenant='A'")
    assert journal.generation("A") > previous
    previous = journal.generation("A")
    journal.redact(row, "user")
    assert journal.generation("A") > previous
    assert journal.get("A", "first")["payload"] == "{}"
    assert journal.generation("B") == 0
    journal.close()


def test_generation_rollback_is_atomic(tmp_path):
    journal = EventJournal(tmp_path / "events.sqlite")
    journal.submit("A", "first", "digest", "user", {}, "mid", True)
    previous = journal.generation("A")
    try:
        with journal.lock, journal.db:
            journal.db.execute("UPDATE events SET status='withdrawn' WHERE tenant='A'")
            raise RuntimeError("crash before commit")
    except RuntimeError:
        pass
    assert journal.generation("A") == previous
    assert journal.get("A", "first")["status"] == "queued"
    journal.close()
