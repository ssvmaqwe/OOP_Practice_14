import json
import os
from typing import Dict, Any, List, Optional
from Core.interfaces import IProfileRepository, IGameRepository


class JsonRepository(IProfileRepository, IGameRepository):
    def __init__(self, filepath: str = "repository.json"):
        self.filepath = filepath

    def _read(self) -> Dict[str, Any]:
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, key: str, value: Any) -> None:
        data = self._read()
        data[key] = value
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_profiles(self) -> List[Dict[str, Any]]:
        return list(self._read().get("characters", []))

    def save_profiles(self, profiles: List[Dict[str, Any]]) -> None:
        self._write("characters", profiles)

    def load_game(self) -> Optional[Dict[str, Any]]:
        state = self._read().get("game_state")
        return state or None

    def save_game(self, config: Dict[str, Any]) -> None:
        self._write("game_state", config)
