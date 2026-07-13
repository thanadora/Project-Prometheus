"""
logger.py — Système de logs de la simulation.

Usage depuis n'importe quel fichier :
    from logger import get_logger
    log = get_logger()
    log.info(world.tick, "Message")

Niveaux disponibles : DEBUG, INFO, WARNING, ERROR
Configuré via config.LOG_LEVEL avant le lancement.
"""

import logging
import os
from collections import deque
from datetime import datetime
import config

_logger_instance = None


class _MemoryHandler(logging.Handler):
    """Garde les derniers messages en mémoire pour que l'UI puisse les afficher
    sans avoir à parser le fichier de log."""

    def __init__(self, capacity=1000):
        super().__init__()
        self.records = deque(maxlen=capacity)
        self._next_seq = 0

    def emit(self, record):
        self.records.append((self._next_seq, record.levelname, self.format(record)))
        self._next_seq += 1


class SimLogger:
    """
    Wrapper autour du logger Python standard.
    Ajoute le tick courant dans chaque message.
    """

    def __init__(self):
        self._log = logging.getLogger("prometheus")
        self._log.setLevel(logging.DEBUG)  # capture tout, filtré par les handlers
        self._log.handlers.clear()

        fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-7s] %(message)s",
            datefmt="%H:%M:%S",
        )

        # ── Handler console ───────────────────────────────────────
        console = logging.StreamHandler()
        console.setLevel(self._level_from_config())
        console.setFormatter(fmt)
        self._log.addHandler(console)

        # ── Handler fichier ───────────────────────────────────────
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath  = f"logs/simulation_{timestamp}.log"
        file_handler = logging.FileHandler(filepath, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)   # tout dans le fichier
        file_handler.setFormatter(fmt)
        self._log.addHandler(file_handler)

        # ── Handler mémoire (pour le panneau de logs dans l'UI) ────
        self._memory = _MemoryHandler(capacity=1000)
        self._memory.setLevel(logging.DEBUG)   # tout en mémoire, l'UI filtre elle-même
        self._memory.setFormatter(fmt)
        self._log.addHandler(self._memory)

        self._log.info(f"[INIT] Logger démarré — niveau console : {config.LOG_LEVEL} — fichier : {filepath}")

    def get_records(self):
        """Retourne tous les messages actuellement en mémoire, sous forme (level, message)."""
        return [(level, msg) for _, level, msg in self._memory.records]

    def get_new_records(self, since_seq):
        """Retourne les messages plus récents que `since_seq` (level, message), et le seq
        le plus récent vu (à repasser au prochain appel). Basé sur des numéros de séquence
        plutôt que sur une longueur brute, donc reste correct même si le buffer mémoire a
        tourné (capacité max atteinte, anciens messages évincés)."""
        new = [(s, level, msg) for s, level, msg in self._memory.records if s > since_seq]
        last_seq = new[-1][0] if new else since_seq
        return [(level, msg) for _, level, msg in new], last_seq

    def get_last_seq(self):
        return self._memory.records[-1][0] if self._memory.records else -1

    def _level_from_config(self):
        return getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    def _fmt(self, tick, msg):
        return f"[TICK {tick:05d}] {msg}"

    def debug(self, tick, msg):
        self._log.debug(self._fmt(tick, msg))

    def info(self, tick, msg):
        self._log.info(self._fmt(tick, msg))

    def warning(self, tick, msg):
        self._log.warning(self._fmt(tick, msg))

    def error(self, tick, msg):
        self._log.error(self._fmt(tick, msg))


def get_logger() -> SimLogger:
    """Retourne l'instance unique du logger (singleton)."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SimLogger()
    return _logger_instance


def reset_logger():
    """Réinitialise le logger (utile si on relance une simulation)."""
    global _logger_instance
    _logger_instance = None