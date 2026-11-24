from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, Dict, Any, List

T = TypeVar('T')


class IRenderer(ABC, Generic[T]):
    @abstractmethod
    def render(self, data: T) -> str:
        pass


class IRenderable(ABC, Generic[T]):
    def __init__(self):
        self._renderer: Optional[IRenderer[T]] = None

    def use_renderer(self, renderer: IRenderer[T]) -> None:
        self._renderer = renderer

    def render(self, renderer: Optional[IRenderer[T]] = None) -> str:
        active_renderer = renderer or self._renderer
        if active_renderer is None:
            return str(self)
        return active_renderer.render(self)  # type: ignore


class ICharacterSource(ABC):
    @abstractmethod
    def fetch(self, name: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_names(self) -> List[str]:
        pass


class IProfileRepository(ABC):
    @abstractmethod
    def load_profiles(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_profiles(self, profiles: List[Dict[str, Any]]) -> None:
        pass


class IGameRepository(ABC):
    @abstractmethod
    def load_game(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_game(self, config: Dict[str, Any]) -> None:
        pass
