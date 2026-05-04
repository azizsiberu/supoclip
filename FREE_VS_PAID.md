# Free vs Paid (SaaS) — Product, Guardrails, and Implementation Checklist

Dokumen ini menjelaskan pembagian fitur **Free** vs **Paid** untuk KlipOS dalam model **SaaS (hosted by us)**, plus checklist implementasi supaya gating beneran kepake di seluruh sistem.

Repo ini sudah punya konsep **hosted vs self-host** lewat flag `SELF_HOST` di backend (`backend/src/config.py`) dan UI billing summary di settings. Dokumen ini fokus ke **plan per-user** (FREE/PRO) dan cost guardrails, bukan distribusi.

> Catatan penting: fitur billing/plan di repo ini saat ini banyak “terkunci” di mode hosted (`SELF_HOST=false`, `monetization_enabled=true`). Tapi untuk SaaS yang punya Free & Paid, tetap butuh **plan per user**, bukan cuma global flag.

---

## 1) Plan Model

Minimal 2 plan:

- **FREE**: cocok untuk coba produk, limit ketat.
- **PRO**: limit lebih tinggi, kualitas lebih bagus, prioritas antrian.

### 1.1 Sumber kebenaran plan

- **Per-user di database** (mis. kolom `users.plan`), bukan ENV.
- Stripe/webhook hanya mengubah nilai plan user.

### 1.2 Plan flags (entitlements)

Contoh entitlements yang dibutuhkan (ini yang nanti dipakai buat gating):

- `max_video_seconds`
- `max_clips_per_task`
- `max_concurrent_tasks`
- `export_max_resolution` (mis. 720p vs 1080p)
- `watermark_enabled`
- `queue_priority`
- `result_retention_hours`
- `broll_enabled` (PEXELS)
- `llm_selection_enabled`

---

## 2) Guardrails Biaya (SaaS)

Komponen biaya terbesar umumnya:

1) **Transcription** (CPU/GPU time, atau API provider)
2) **LLM analysis/segment selection**
3) **Rendering** (ffmpeg time)
4) **Storage + bandwidth**

### 2.1 Default limit yang disarankan

Angka di bawah ini baseline aman untuk SaaS awal; sesuaikan setelah kamu punya telemetry cost.

| Dimensi | FREE (default) | PRO (default) |
|---|---:|---:|
| Max input video durasi / task | 5–10 menit | 30–120 menit |
| Concurrent tasks / user | 1 | 2–5 |
| Clips / task | 3–5 | 7–20 |
| Durasi clip | 10–30s | 10–60s |
| Export resolution | 720p | 1080p (opsional 4K) |
| Watermark | ON | OFF |
| Queue priority | normal/low | high |
| Retention hasil (clips) | 24–72 jam | 7–30 hari |
| Retention upload/input | 24 jam | 7 hari |

> Dalam repo ini, batas global sekarang ada di ENV `MAX_VIDEO_DURATION`, `MAX_CLIPS`, `CLIP_DURATION` (`backend/src/config.py`). Untuk SaaS Free vs Paid, value ini sebaiknya jadi **limit maksimum sistem**, sedangkan limit per plan dievaluasi per user.

---

## 3) Pipeline Defaults (nyambung dengan repo ini)

Repo ini punya:

- `ffmpeg` untuk rendering (`backend/Dockerfile`)
- YouTube download provider `yt-dlp` default (gratis) + opsi Apify (berbayar) (`backend/README.md`)
- B-roll provider Pexels (`backend/src/broll.py`) gated oleh `PEXELS_API_KEY`
- LLM config via `LLM` + keys (`backend/src/config.py`, `QUICKSTART.md`)

### 3.1 YouTube download & metadata

**FREE:**
- Default `YOUTUBE_DOWNLOAD_PROVIDER=yt_dlp` (gratis)
- Metadata provider `yt_dlp` default

**PRO:**
- Opsional enable fallback premium (mis. Apify) kalau kamu memang mau “higher success rate”.

**Guardrail:**
- Jangan jadikan provider berbayar sebagai default untuk semua user.

### 3.2 B-roll

Di repo, B-roll fetch cuma jalan kalau `PEXELS_API_KEY` ada.

**FREE:**
- B-roll OFF (atau limited sangat ketat)

**PRO:**
- B-roll ON (dengan quota)

**Guardrail:**
- Tambah gating per plan sebelum memanggil Pexels (bukan cuma cek API key).

### 3.3 LLM-based selection

**FREE:**
- Heuristic selection (tanpa LLM mahal) / atau LLM sangat dibatasi credit.

**PRO:**
- LLM-based highlight + titles

---

## 4) Konfigurasi: Hosted vs Plan (penting)

Repo sudah punya flag:

- `SELF_HOST` (default `True`)
- `monetization_enabled = not self_host` (`backend/src/config.py`)

Untuk SaaS yang punya Free & Paid:

- Set `SELF_HOST=false` untuk **mengaktifkan hosted/billing flows**
- Tambahkan konsep **plan per user** (FREE/PRO)

> Jangan pakai `APP_PLAN=free|pro` global. Itu cocok untuk “dua distribusi”, tapi bukan untuk SaaS multi-user.

---

## 5) Implementation Checklist (yang harus dicek & diubah di seluruh app)

Bagian ini adalah checklist end-to-end supaya free/paid beneran ke-apply.

### 5.1 Database & User model

- [ ] Tambah field user: `plan` (FREE/PRO)
- [ ] Tambah field optional: `plan_expires_at`, `trial_credits_seconds`
- [ ] Buat usage ledger (disarankan): catat pemakaian “processing seconds” per user per periode
- [ ] Pastikan signup/default user = FREE

### 5.2 Backend API gating (Wajib server-side)

Semua endpoint yang memicu biaya harus enforce:

- [ ] **Create task**: cek durasi input, max clips, mode processing
- [ ] **Queue**: cek concurrency per user + set priority
- [ ] **Render/export**: cek resolution, watermark rule, rerender limit
- [ ] **B-roll**: cek `PEXELS_API_KEY` + entitlement plan
- [ ] **LLM calls**: cek entitlement plan + quota

Error shape yang konsisten:

- [ ] `upgrade_required`
- [ ] `plan_limit_exceeded`
- [ ] `quota_exceeded`

### 5.3 Backend config yang perlu ditinjau (repo-specific)

Di `backend/src/config.py` sudah ada:

- `MAX_VIDEO_DURATION`
- `MAX_CLIPS`
- `CLIP_DURATION`
- `FREE_PLAN_TASK_LIMIT`
- `PRO_PLAN_TASK_LIMIT`

Checklist:

- [ ] Pastikan `FREE_PLAN_TASK_LIMIT` / `PRO_PLAN_TASK_LIMIT` dipakai dari **plan user**, bukan hardcode global.
- [ ] Pisahkan “limit sistem” (ENV) vs “limit plan” (DB/entitlements).

### 5.4 Worker / queue priority

Repo pakai ARQ worker (lihat `CLAUDE.md`).

- [ ] Tambah `priority` pada job enqueue berdasarkan plan
- [ ] Batasi retry untuk Free
- [ ] Terapkan queued timeout (`QUEUED_TASK_TIMEOUT_SECONDS`) per plan jika perlu

### 5.5 Storage & retention

- [ ] Tambah `expires_at` untuk uploads dan outputs
- [ ] Tambah cleanup job terjadwal
- [ ] Retention berbeda per plan

### 5.6 Frontend UI/UX

Di repo, settings page sudah menampilkan billing summary.

- [ ] Tampilkan plan badge (FREE/PRO) + quota meter
- [ ] Saat user kena limit: tampilkan CTA upgrade (Stripe checkout)
- [ ] Feature gating di UI (tapi tetap enforce di backend)

### 5.7 Billing (Stripe) & Webhooks

- [ ] Stripe subscription untuk PRO
- [ ] Webhook update `users.plan`
- [ ] Portal untuk manage subscription
- [ ] Email lifecycle via Resend (repo sudah mention ini)

### 5.8 Observability

- [ ] Log per task: input seconds, clip count, provider (yt_dlp/apify), broll used, llm used
- [ ] Dashboard “cost per plan” + cache hit rate + abuse detection

---

## 6) Repo status note (biar sesuai realita repo)

Hasil pembacaan cepat repo (berdasarkan code search; hasil bisa tidak lengkap karena search dibatasi 10 result):

- Hosted/self-host sudah ada lewat `SELF_HOST`.
- Ada billing UI + backend config untuk monetization.
- Ada provider berbayar yang sudah dibuat optional (Apify, Pexels).

Kalau kamu mau dokumen ini lebih “tajam” sesuai file yang tepat, perlu kita mapping:

- endpoint create task mana yang paling utama (route FastAPI)
- service mana yang memanggil LLM
- tempat enqueue ARQ job

Link untuk lihat hasil code search lebih lengkap:
https://github.com/azizsiberu/klipos/search?q=APP_PLAN+OR+plan+OR+subscription+OR+stripe+OR+monetization+OR+SELF_HOST+OR+FREE_PLAN_TASK_LIMIT+OR+PRO_PLAN_TASK_LIMIT&type=code
