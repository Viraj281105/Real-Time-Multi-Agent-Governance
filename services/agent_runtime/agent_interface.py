# services/agent_runtime/agent_interface.py
from typing import Dict, Any
import abc

class AgentInterface(abc.ABC):
    agent_id: str

    @abc.abstractmethod
    async def on_tick(self, tick: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def on_event(self, event: Dict[str, Any]) -> None:
        raise NotImplementedError
