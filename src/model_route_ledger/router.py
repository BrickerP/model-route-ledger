"""Rule-based router: cheap steps go to Haiku, voice/judgment to Sonnet, code to Opus."""
import json
from dataclasses import dataclass, field


@dataclass
class Policy:
    default: str = "sonnet-5.5"
    routes: dict = field(default_factory=dict)   # step kind -> model
    never_downgrade: list = field(default_factory=list)  # kinds that must stay >= default
    max_haiku_prompt: int = 100_000  # flag Haiku prompts that would cross the price cliff

    @classmethod
    def load(cls, path: str) -> "Policy":
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return cls(**d)


RANK = {"haiku-5.5": 0, "sonnet-5.5": 1, "opus-5.5": 2}


def route(policy: Policy, step: dict, haiku_inflation: float) -> tuple[str, str]:
    """Return (model, reason)."""
    kind = step.get("kind", "unknown")
    model = policy.routes.get(kind, policy.default)
    if kind in policy.never_downgrade and RANK[model] < RANK[policy.default]:
        return policy.default, f"{kind}: never_downgrade"
    if model == "haiku-5.5":
        prompt = int((step["input_tokens"] + step.get("cached_tokens", 0)) * haiku_inflation)
        if prompt > policy.max_haiku_prompt:
            # Still cheaper than Sonnet, but 5x the sub-cliff price: flag it so you trim context.
            return model, f"{kind}: haiku prompt {prompt:,} over cliff, trim context"
    return model, f"{kind} -> {model}"
