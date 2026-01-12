from typing import Callable, Dict, Optional


class SharedVarsManager:
    """Singleton-like manager to keep shared vars consistent across executors."""

    _instance: Optional["SharedVarsManager"] = None

    def __init__(self) -> None:
        self.store: Dict[str, object] = {}
        self._subscribers: list[Callable[[Dict[str, object]], None]] = []

    @classmethod
    def instance(cls) -> "SharedVarsManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_store(self, mapping: Optional[Dict[str, object]]) -> Dict[str, object]:
        if mapping is None:
            self.store = {}
        else:
            self.store = mapping
        self._notify()
        return self.store

    def all(self) -> Dict[str, object]:
        return self.store

    def get(self, key: str, default=None):
        return self.store.get(key, default)

    def set(self, key: str, value: object) -> None:
        self.store[key] = value
        self._notify()

    def subscribe(self, callback: Callable[[Dict[str, object]], None]) -> None:
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Dict[str, object]], None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _notify(self) -> None:
        for callback in list(self._subscribers):
            try:
                callback(dict(self.store))
            except Exception:
                continue
