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
from datetime import datetime
import config

_logger_instance = None


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

        self._log.info(f"[INIT] Logger démarré — niveau console : {config.LOG_LEVEL} — fichier : {filepath}")

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