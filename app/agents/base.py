from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):
    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    @abstractmethod
    def run(self, input_data: Any) -> Any:
        pass

class PlannerAgentContract(BaseAgent):
    def __init__(self):
        super().__init__("PlannerAgent")

    @abstractmethod
    def run(self, input_data: Any) -> Any:
        pass

class ResearchAgentContract(BaseAgent):
    def __init__(self):
        super().__init__("ResearchAgent")

    @abstractmethod
    def run(self, input_data: Dict) -> Any:
        # Input: destination, interests, duration
        pass

class PreferenceAgentContract(BaseAgent):
    def __init__(self):
        super().__init__("PreferenceAgent")

    @abstractmethod
    def run(self, input_data: Dict) -> float:
        # Input: user interests, candidate attractions
        pass

class TransportAgentContract(BaseAgent):
    def __init__(self):
        super().__init__("TransportAgent")

    @abstractmethod
    def run(self, input_data: Dict) -> Dict:
        pass

class AccommodationAgentContract(BaseAgent):
    def __init__(self):
        super().__init__("AccommodationAgent")

    @abstractmethod
    def run(self, input_data: Dict) -> Any:
        pass

class BudgetAgentContract(BaseAgent):
    def __init__(self):
        super().__init__("BudgetAgent")

    @abstractmethod
    def run(self, input_data: Any) -> Dict:
        pass

class ConstraintAgentContract(BaseAgent):
    def __init__(self):
        super().__init__("ConstraintAgent")

    @abstractmethod
    def run(self, input_data: Any) -> Dict:
        pass

class OptimizationAgentContract(BaseAgent):
    def __init__(self):
        super().__init__("OptimizationAgent")

    @abstractmethod
    def run(self, input_data: Any) -> Any:
        pass
