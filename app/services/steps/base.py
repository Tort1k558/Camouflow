from dataclasses import dataclass
from typing import Optional


@dataclass
class StepResult:
    status: str
    jump_label: Optional[str] = None
    stop_reason: Optional[str] = None

    @classmethod
    def next(cls) -> "StepResult":
        return cls(status="next")

    @classmethod
    def jump(cls, label: str) -> "StepResult":
        return cls(status="jump", jump_label=label)

    @classmethod
    def stop(cls, reason: str) -> "StepResult":
        return cls(status="stop", stop_reason=reason)

    @classmethod
    def end(cls) -> "StepResult":
        return cls(status="end")
