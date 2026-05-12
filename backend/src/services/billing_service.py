from __future__ import annotations

from datetime import datetime, timezone
import calendar
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Config, get_config
from .entitlement_service import EntitlementService


class BillingLimitExceeded(Exception):
    def __init__(self, summary: dict[str, Any], code: str):
        super().__init__("Billing limit reached")
        self.summary = summary
        self.code = code


class BillingService:
    def __init__(self, db: AsyncSession, config: Config | None = None):
        self.db = db
        self.config = config or get_config()
        self.entitlements = EntitlementService(self.config)

    @staticmethod
    def _month_window(now: datetime) -> tuple[datetime, datetime]:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        _, day_count = calendar.monthrange(start.year, start.month)
        end = start.replace(
            day=day_count, hour=23, minute=59, second=59, microsecond=999999
        )
        return start, end

    async def _load_user_billing_row(self, user_id: str) -> dict[str, Any]:
        result = await self.db.execute(
            text(
                """
                SELECT
                    plan,
                    subscription_status,
                    billing_period_start,
                    billing_period_end,
                    trial_ends_at,
                    trial_credits_seconds,
                    plan_expires_at
                FROM users
                WHERE id = :user_id
                """
            ),
            {"user_id": user_id},
        )
        row = result.fetchone()
        if not row:
            raise ValueError("User not found")

        return {
            "plan": (row.plan or "free").lower(),
            "subscription_status": (row.subscription_status or "inactive").lower(),
            "billing_period_start": row.billing_period_start,
            "billing_period_end": row.billing_period_end,
            "trial_ends_at": row.trial_ends_at,
            "trial_credits_seconds": getattr(row, "trial_credits_seconds", None),
            "plan_expires_at": getattr(row, "plan_expires_at", None),
        }

    async def _count_tasks(
        self, user_id: str, period_start: datetime, period_end: datetime
    ) -> int:
        result = await self.db.execute(
            text(
                """
                SELECT COUNT(*) AS total
                FROM tasks
                WHERE user_id = :user_id
                  AND created_at >= :period_start
                  AND created_at <= :period_end
                """
            ),
            {
                "user_id": user_id,
                "period_start": period_start,
                "period_end": period_end,
            },
        )
        row = result.fetchone()
        return int(row.total) if row and row.total is not None else 0

    async def _sum_usage_seconds(
        self, user_id: str, period_start: datetime, period_end: datetime
    ) -> int:
        result = await self.db.execute(
            text(
                """
                SELECT COALESCE(SUM(usage_seconds), 0) AS total
                FROM usage_ledger
                WHERE user_id = :user_id
                  AND created_at >= :period_start
                  AND created_at <= :period_end
                """
            ),
            {
                "user_id": user_id,
                "period_start": period_start,
                "period_end": period_end,
            },
        )
        row = result.fetchone()
        return int(row.total) if row and row.total is not None else 0

    async def get_usage_summary(self, user_id: str) -> dict[str, Any]:
        if not self.config.monetization_enabled:
            return {
                "monetization_enabled": False,
                "plan": "self_host",
                "subscription_status": "inactive",
                "period_start": None,
                "period_end": None,
                "usage_count": 0,
                "usage_limit": None,
                "remaining": None,
                "can_create_task": True,
                "upgrade_required": False,
                "reason": None,
            }

        row = await self._load_user_billing_row(user_id)
        now = datetime.now(timezone.utc)

        start = row.get("billing_period_start")
        end = row.get("billing_period_end")
        if not start or not end:
            start, end = self._month_window(now)

        usage_count = await self._count_tasks(user_id, start, end)

        plan = row["plan"]
        status = row["subscription_status"]
        is_paid = plan == "pro" and status in {"active", "trialing"}
        entitlements = self.entitlements.get_entitlements(plan, is_paid)
        usage_seconds = await self._sum_usage_seconds(user_id, start, end)

        usage_limit = entitlements.max_task_limit
        unlimited = usage_limit is None
        can_create_by_task_count = unlimited or usage_count < usage_limit
        remaining = None if unlimited else max(usage_limit - usage_count, 0)

        free_credit_limit = (
            int(row.get("trial_credits_seconds") or self.config.free_plan_credits_seconds)
            if entitlements.plan == "free"
            else None
        )
        free_remaining_seconds = (
            max(int(free_credit_limit) - usage_seconds, 0)
            if free_credit_limit is not None
            else None
        )
        can_create_by_credits = (
            True if free_remaining_seconds is None else free_remaining_seconds > 0
        )
        can_create = can_create_by_task_count and can_create_by_credits
        reason = None
        error_code = None
        if not can_create_by_credits:
            reason = "Free plan credits exhausted"
            error_code = "quota_exceeded"
        elif not can_create_by_task_count:
            reason = "Plan usage limit reached"
            error_code = "plan_limit_exceeded"

        return {
            "monetization_enabled": True,
            "plan": entitlements.plan,
            "subscription_status": status,
            "period_start": start,
            "period_end": end,
            "trial_ends_at": row.get("trial_ends_at"),
            "usage_count": usage_count,
            "usage_seconds": usage_seconds,
            "usage_limit": None if unlimited else usage_limit,
            "remaining": remaining,
            "credits_limit_seconds": free_credit_limit,
            "remaining_credits_seconds": free_remaining_seconds,
            "can_use_broll": entitlements.can_use_broll,
            "can_use_llm": entitlements.can_use_llm,
            "can_create_task": can_create,
            "upgrade_required": not can_create,
            "error_code": error_code,
            "reason": reason,
        }

    async def assert_can_create_task(self, user_id: str) -> None:
        summary = await self.get_usage_summary(user_id)
        if summary.get("can_create_task"):
            return
        error_code = summary.get("error_code")
        if error_code == "quota_exceeded":
            raise BillingLimitExceeded(summary, "quota_exceeded")
        if error_code == "plan_limit_exceeded":
            raise BillingLimitExceeded(summary, "plan_limit_exceeded")
        raise BillingLimitExceeded(summary, "upgrade_required")

    async def assert_feature_access(self, user_id: str, feature: str) -> None:
        summary = await self.get_usage_summary(user_id)
        if feature == "broll" and summary.get("can_use_broll"):
            return
        if feature == "llm" and summary.get("can_use_llm"):
            return
        raise BillingLimitExceeded(
            summary | {"reason": f"{feature} requires upgrade"},
            "upgrade_required",
        )
