import io
import logging
import sys
import threading
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest

from promptsmith.runtime_log import RuntimeLog


def test_all_levels_exception_chain_and_secrets_reach_file_and_history(tmp_path):
    logs = RuntimeLog(tmp_path).start()
    logs.register_secret("fixture-secret-value")
    try:
        logger = logging.getLogger("promptsmith.test")
        for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
            logger.log(level, "level=%s 中文日志", level)
        try:
            try:
                raise ValueError("underlying failure fixture-secret-value")
            except ValueError as exc:
                raise RuntimeError("outer failure") from exc
        except RuntimeError:
            logger.exception("test exception chain; Authorization: Bearer other-secret")
        assert not list(tmp_path.iterdir())
        content = logs.save().read_text(encoding="utf-8")
        history = "\n".join(entry.text for entry in logs.entries_after())
        for text in (content, history):
            assert all(level in text for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))
            assert "Traceback" in text and "ValueError" in text and "RuntimeError" in text
            assert "direct cause" in text and "test_runtime_log.py" in text
            assert "fixture-secret-value" not in text and "other-secret" not in text
            assert "中文日志" in text and "[REDACTED]" in text
            assert "[REDACTED]]" not in text
    finally:
        logs.close()


def test_concurrent_logging_is_complete_ordered_and_bounded(tmp_path):
    logs = RuntimeLog(tmp_path, history_limit=35).start()
    try:
        def work(index):
            for line in range(40):
                logging.getLogger("promptsmith.worker-test").info("worker-%s-line-%s", index, line)
        threads = [threading.Thread(target=work, args=(i,), name=f"TestWorker-{i}") for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        content = logs.save().read_text(encoding="utf-8")
        assert sum("worker-" in line for line in content.splitlines()) == 160
        assert "TestWorker-3/INFO" in content
        entries = logs.entries_after()
        assert len(entries) == 35
        assert [e.sequence for e in entries] == sorted(set(e.sequence for e in entries))
        assert len(logs.entries_after(entries[-2].sequence)) == 1
    finally:
        logs.close()


def test_full_run_save_exceeds_display_history_without_truncation(tmp_path):
    logs = RuntimeLog(tmp_path / "logs", history_limit=2).start()
    try:
        for index in range(20):
            logging.getLogger("promptsmith.archive").debug("archive-%s %s", index, "x" * 200)
        assert not logs.directory.exists()
        logging.getLogger("promptsmith.archive").error("long-diagnostic:" + "y" * 5000 + ":end")
        content = logs.save().read_text(encoding="utf-8")
        assert "y" * 5000 + ":end" in content
        assert sum("archive-" in line for line in content.splitlines()) == 20
        assert len(logs.entries_after()) == 2
    finally:
        logs.close()


def test_stream_warning_and_uncaught_hooks_are_captured_and_restored(tmp_path, monkeypatch):
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    hooks_seen = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: hooks_seen.append("process"))
    monkeypatch.setattr(threading, "excepthook", lambda args: hooks_seen.append("thread"))
    monkeypatch.setattr(sys, "unraisablehook", lambda args: hooks_seen.append("unraisable"))
    previous = (sys.excepthook, threading.excepthook, warnings.showwarning, sys.unraisablehook)
    logs = RuntimeLog(tmp_path).start(capture_process=True)
    try:
        print("standard output line")
        sys.stderr.write("standard error line\n")
        warnings.showwarning("warning detail", RuntimeWarning, "test_source.py", 19)
        try:
            raise LookupError("hook failure")
        except LookupError:
            triple = sys.exc_info()
            sys.excepthook(*triple)
            threading.excepthook(SimpleNamespace(exc_type=triple[0], exc_value=triple[1],
                                                exc_traceback=triple[2], thread=threading.current_thread()))
            sys.unraisablehook(SimpleNamespace(exc_type=triple[0], exc_value=triple[1],
                                              exc_traceback=triple[2], err_msg="cleanup failure"))
        sys.stdout.write("partial without newline")
    finally:
        logs.close()
    assert sys.stdout is stdout and sys.stderr is stderr
    assert (sys.excepthook, threading.excepthook, warnings.showwarning, sys.unraisablehook) == previous
    assert hooks_seen == ["process", "thread", "unraisable"]
    assert not list(tmp_path.iterdir())
    content = logs.save().read_text(encoding="utf-8")
    for text in ("standard output line", "standard error line", "RuntimeWarning", "test_source.py:19",
                 "Uncaught process exception", "Uncaught thread exception", "Unraisable exception",
                 "cleanup failure", "LookupError", "partial without newline"):
        assert text in content


def test_unwritable_directory_keeps_memory_logging(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("blocked")
    logs = RuntimeLog(blocker / "logs").start()
    try:
        logging.getLogger("promptsmith.fallback").error("still available")
        assert not logs.file_error
        assert "still available" in logs.entries_after()[-1].text
        with pytest.raises(OSError):
            logs.save()
        assert logs.file_error and logs.path is None
        assert any("saving failed" in entry.text for entry in logs.entries_after())
        assert "Traceback" in logs.entries_after()[-1].text
    finally:
        logs.close()


def test_save_failure_keeps_full_history_and_retry_succeeds(tmp_path, monkeypatch):
    logs = RuntimeLog(tmp_path).start()
    replace = Path.replace
    def fail(*args):
        raise OSError("disk full")
    try:
        logging.getLogger("promptsmith.fallback").warning("record survives")
        with monkeypatch.context() as failing:
            failing.setattr(Path, "replace", fail)
            with pytest.raises(OSError, match="disk full"):
                logs.save()
        assert logs.file_error == "disk full"
        assert logs.path is None and not list(tmp_path.iterdir())
        assert any("record survives" in entry.text for entry in logs.entries_after())
        assert any("saving failed" in entry.text for entry in logs.entries_after())
        assert "OSError: disk full" in logs.entries_after()[-1].text
        assert "Traceback" in logs.entries_after()[-1].text
        assert Path.replace is replace
        content = logs.save().read_text(encoding="utf-8")
        assert not logs.file_error
        assert "record survives" in content and "OSError: disk full" in content
    finally:
        logs.close()


def test_close_releases_handler_without_closing_existing_handlers(tmp_path):
    root = logging.getLogger()
    before = list(root.handlers)
    old_level = root.level
    logs = RuntimeLog(tmp_path).start()
    logs.close()
    logs.close()
    assert root.handlers == before
    assert root.level == old_level


def test_partial_worker_output_and_new_stream_handler_do_not_recurse(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    logs = RuntimeLog(tmp_path).start(capture_process=True)
    handler = logging.StreamHandler(sys.stderr)
    logger = logging.getLogger("promptsmith.stream-test")
    logger.addHandler(handler)
    try:
        thread = threading.Thread(target=lambda: sys.stdout.write("worker partial"))
        thread.start()
        thread.join()
        logger.error("handler writes captured stderr")
    finally:
        logger.removeHandler(handler)
        handler.close()
        logs.close()
    content = logs.save().read_text(encoding="utf-8")
    assert "worker partial" in content
    assert content.count("handler writes captured stderr") == 2


def test_local_skill_io_failure_is_logged_with_traceback(tmp_path):
    from promptsmith.local_skill_search import _read_skill

    logs = RuntimeLog(tmp_path / "logs").start()
    try:
        info, error = _read_skill(tmp_path / "missing" / "SKILL.md")
        assert info is None and error
        content = logs.save().read_text(encoding="utf-8")
        assert "Cannot read Skill file" in content
        assert "FileNotFoundError" in content and "Traceback" in content
    finally:
        logs.close()


def test_real_uncaught_thread_exception_reaches_file(tmp_path, monkeypatch):
    monkeypatch.setattr(threading, "excepthook", lambda args: None)
    logs = RuntimeLog(tmp_path).start(capture_process=True)
    try:
        def crash():
            raise RuntimeError("real uncaught worker failure")
        worker = threading.Thread(target=crash, name="CrashWorker")
        worker.start()
        worker.join()
        content = logs.save().read_text(encoding="utf-8")
        assert "Uncaught thread exception: CrashWorker" in content
        assert "RuntimeError: real uncaught worker failure" in content and "Traceback" in content
    finally:
        logs.close()


def test_no_automatic_creation_or_changes_to_existing_logs(tmp_path):
    absent = tmp_path / "absent" / "logs"
    logs = RuntimeLog(absent).start()
    logs.record("test", logging.ERROR, "memory only")
    logs.close()
    assert logs.path is None and not absent.exists()
    existing = tmp_path / "existing"
    existing.mkdir()
    old_file = existing / "latest.log"
    old_file.write_bytes(b"previous run\n")
    stat = old_file.stat()
    logs = RuntimeLog(existing).start()
    logs.record("test", logging.DEBUG, "new run")
    logs.close()
    assert old_file.read_bytes() == b"previous run\n"
    assert old_file.stat().st_mtime_ns == stat.st_mtime_ns
    assert list(existing.iterdir()) == [old_file]


def test_repeat_saves_are_complete_distinct_immutable_snapshots(tmp_path):
    logs = RuntimeLog(tmp_path).start()
    try:
        logs.record("test", logging.INFO, "before first click")
        first = logs.save()
        first_bytes = first.read_bytes()
        first_time = first.stat().st_mtime_ns
        logs.record("test", logging.ERROR, "after first click")
        assert first.read_bytes() == first_bytes and first.stat().st_mtime_ns == first_time
        second = logs.save()
        assert first != second
        assert first.read_bytes() == first_bytes
        content = second.read_text(encoding="utf-8")
        assert "before first click" in content and "after first click" in content
        assert "Manual log snapshot saved" in content
        assert len(list(tmp_path.glob("*.log"))) == 2
    finally:
        logs.close()
    assert first.read_bytes() == first_bytes
    assert "Runtime logging stopped" not in second.read_text(encoding="utf-8")


def test_save_flushes_partial_streams_and_redacts_late_registered_secret(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    logs = RuntimeLog(tmp_path).start(capture_process=True)
    try:
        logs.record("test", logging.INFO, "early late-registered-value")
        logs.register_secret("late-registered-value")
        sys.stdout.write("pending output without newline")
        content = logs.save().read_text(encoding="utf-8")
        assert "pending output without newline" in content
        assert "late-registered-value" not in content and "early [REDACTED]" in content
    finally:
        logs.close()


def test_logging_during_save_is_not_lost_and_next_snapshot_includes_it(tmp_path, monkeypatch):
    logs = RuntimeLog(tmp_path).start()
    replace = Path.replace
    try:
        logs.record("test", logging.INFO, "before snapshot")
        def replace_with_concurrent_log(source, destination):
            worker = threading.Thread(target=lambda: logs.record("test", logging.INFO, "during snapshot"))
            worker.start()
            worker.join(timeout=2)
            assert not worker.is_alive()
            return replace(source, destination)
        with monkeypatch.context() as during_save:
            during_save.setattr(Path, "replace", replace_with_concurrent_log)
            first = logs.save()
        assert "during snapshot" not in first.read_text(encoding="utf-8")
        content = logs.save().read_text(encoding="utf-8")
        assert "before snapshot" in content and "during snapshot" in content
    finally:
        logs.close()


def test_repeated_redaction_keeps_marker_and_removes_bracketed_credentials(tmp_path):
    logs = RuntimeLog(tmp_path)
    try:
        text = logs.redact("api_key=[private-value] Authorization: Bearer [another-private-value]")
        assert "private-value" not in text
        assert logs.redact(text) == text
        assert "[REDACTED]]" not in text
    finally:
        logs.close()


def test_partial_write_failure_removes_temp_and_preserves_previous_snapshot(tmp_path, monkeypatch):
    logs = RuntimeLog(tmp_path).start()
    try:
        first = logs.save()
        first_bytes = first.read_bytes()
        logs.record("test", logging.ERROR, "pending record after successful save")
        redact = logs.redact
        writes = 0
        def fail_during_write(text):
            nonlocal writes
            writes += 1
            if writes == 3:
                raise OSError("disk full during write")
            return redact(text)
        with monkeypatch.context() as failing:
            failing.setattr(logs, "redact", fail_during_write)
            with pytest.raises(OSError, match="disk full during write"):
                logs.save()
        assert logs.path == first and first.read_bytes() == first_bytes
        assert list(tmp_path.iterdir()) == [first]
        content = logs.save().read_text(encoding="utf-8")
        assert "pending record after successful save" in content
        assert "OSError: disk full during write" in content and "Traceback" in content
    finally:
        logs.close()
