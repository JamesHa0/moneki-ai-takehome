"""对话历史。"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Optional

MAX_TURNS = 6
MAX_SESSIONS = 500


class SessionStore:
    """最近几轮对话，够解追问就行。"""

    def __init__(self, max_sessions: int = MAX_SESSIONS, max_turns: int = MAX_TURNS) -> None:
        self._turns: "OrderedDict[str, list[dict]]" = OrderedDict()
        self._lock = threading.Lock()
        self.max_sessions = max_sessions
        self.max_turns = max_turns

    @staticmethod
    def _key(session_id: Optional[str]) -> str:
        return session_id or ""

    def history(self, session_id: Optional[str]) -> list[dict]:
        with self._lock:
            key = self._key(session_id)
            turns = self._turns.get(key)
            if turns is None:
                return []
            self._turns.move_to_end(key)
            return list(turns)

    def append(self, session_id: Optional[str], turn: dict) -> None:
        with self._lock:
            key = self._key(session_id)
            turns = self._turns.setdefault(key, [])
            self._turns.move_to_end(key)
            turns.append(turn)
            del turns[: max(0, len(turns) - max(0, self.max_turns))]
            while len(self._turns) > max(0, self.max_sessions):
                self._turns.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._turns.clear()
