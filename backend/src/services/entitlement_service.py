from __future__ import annotations

from dataclasses import dataclass

from ..config import Config, get_config


@dataclass
class PlanEntitlements:
    plan: str
    can_use_broll: bool
    can_use_llm: bool
    max_task_limit: int | None


class EntitlementService:
    def __init__(self, config: Config | None = None):
        self.config = config or get_config()

    def get_entitlements(self, plan: str, is_paid: bool) -> PlanEntitlements:
        normalized_plan = (plan or "free").lower()
        if normalized_plan == "pro" and is_paid:
            pro_limit = self.config.pro_plan_task_limit
            return PlanEntitlements(
                plan="pro",
                can_use_broll=True,
                can_use_llm=True,
                max_task_limit=None if pro_limit <= 0 else pro_limit,
            )

        free_limit = self.config.free_plan_task_limit
        return PlanEntitlements(
            plan="free",
            can_use_broll=False,
            can_use_llm=True,
            max_task_limit=None if free_limit <= 0 else free_limit,
        )
