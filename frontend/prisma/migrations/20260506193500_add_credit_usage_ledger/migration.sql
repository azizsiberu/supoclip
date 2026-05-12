-- Add credit lifecycle fields to users
ALTER TABLE "users"
ADD COLUMN IF NOT EXISTS "trial_credits_seconds" INTEGER NOT NULL DEFAULT 1800,
ADD COLUMN IF NOT EXISTS "plan_expires_at" TIMESTAMPTZ;

-- Track per-task usage for billing and quota enforcement
CREATE TABLE IF NOT EXISTS "usage_ledger" (
  "id" TEXT NOT NULL,
  "user_id" TEXT NOT NULL,
  "task_id" TEXT,
  "usage_seconds" INTEGER NOT NULL,
  "source_type" VARCHAR(20),
  "provider" VARCHAR(50),
  "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "usage_ledger_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "usage_ledger_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS "usage_ledger_user_id_created_at_idx"
ON "usage_ledger"("user_id", "created_at");

CREATE INDEX IF NOT EXISTS "usage_ledger_task_id_idx"
ON "usage_ledger"("task_id");
