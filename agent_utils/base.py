"""Agent base data structures"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
import time


class AgentState(Enum):
    """Agent state"""
    IDLE = "idle"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    VALIDATING = "validating"
    FIXING = "fixing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ValidationResult:
    """Validation result"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __str__(self):
        if self.is_valid:
            return "Validation passed"
        return f"Validation failed:\n" + "\n".join(f"  - {e}" for e in self.errors)


@dataclass
class AgentContext:
    """Agent context"""
    state: AgentState = AgentState.IDLE
    image_path: Optional[str] = None
    current_output: Optional[str] = None
    parsed_json: Optional[Dict] = None
    validation_result: Optional[ValidationResult] = None
    iteration: int = 0
    max_iterations: int = 3
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_history(self, action: str, detail: Any = None):
        self.history.append({
            "iteration": self.iteration,
            "state": self.state.value,
            "action": action,
            "detail": detail,
            "timestamp": time.time()
        })








