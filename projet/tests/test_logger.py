import os

import pytest

import logger as logger_module
from logger import get_logger, reset_logger


@pytest.fixture(autouse=True)
def _isolated_logger(tmp_path, monkeypatch):
    """Chaque test tourne dans un dossier temporaire (le logger écrit un
    fichier réel sous logs/) et repart d'un logger fraîchement réinitialisé,
    pour ne pas polluer le vrai dossier de logs du projet ni fuiter d'état
    entre les tests."""
    monkeypatch.chdir(tmp_path)
    reset_logger()
    yield
    reset_logger()


class TestSingleton:
    def test_get_logger_returns_same_instance(self):
        assert get_logger() is get_logger()

    def test_reset_logger_creates_a_new_instance(self):
        first = get_logger()
        reset_logger()
        second = get_logger()
        assert first is not second


class TestFileCreation:
    def test_creates_a_log_file_under_logs_directory(self):
        get_logger()
        assert os.path.isdir("logs")
        files = os.listdir("logs")
        assert len(files) == 1
        assert files[0].startswith("simulation_")
        assert files[0].endswith(".log")


class TestMemoryRecords:
    def test_info_message_is_recorded_with_tick_prefix(self):
        log = get_logger()
        log.info(42, "hello world")
        records = log.get_records()
        assert any("TICK 00042" in msg and "hello world" in msg for _, msg in records)

    def test_levels_are_recorded_correctly(self):
        log = get_logger()
        log.debug(1, "d")
        log.info(1, "i")
        log.warning(1, "w")
        log.error(1, "e")
        levels = [level for level, _ in log.get_records()]
        assert "DEBUG" in levels
        assert "INFO" in levels
        assert "WARNING" in levels
        assert "ERROR" in levels

    def test_get_new_records_only_returns_records_after_given_seq(self):
        log = get_logger()
        log.info(1, "first")
        seq_after_first = log.get_last_seq()
        log.info(2, "second")
        log.info(3, "third")
        new_records, last_seq = log.get_new_records(seq_after_first)
        messages = [msg for _, msg in new_records]
        assert any("second" in m for m in messages)
        assert any("third" in m for m in messages)
        assert not any("first" in m for m in messages)
        assert last_seq == log.get_last_seq()

    def test_get_new_records_returns_empty_when_nothing_new(self):
        log = get_logger()
        log.info(1, "only message")
        last = log.get_last_seq()
        new_records, returned_seq = log.get_new_records(last)
        assert new_records == []
        assert returned_seq == last

    def test_get_last_seq_starts_at_zero_because_of_the_init_message(self):
        # SimLogger.__init__ loggue lui-même un message "[INIT] Logger
        # démarré..." dès sa création, donc il n'existe pas d'état où le
        # buffer mémoire est réellement vide après get_logger().
        log = get_logger()
        assert log.get_last_seq() == 0
        assert len(log.get_records()) == 1


class TestFormatting:
    def test_tick_is_zero_padded_to_five_digits(self):
        log = get_logger()
        log.info(7, "x")
        _, msg = log.get_records()[-1]
        assert "[TICK 00007]" in msg
