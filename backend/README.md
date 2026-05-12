# Backend Docs

## Requirements

Ensure you have `ffmpeg` installed.

```
# MacOS
brew install ffmpeg

# Linux (Ubuntu)
sudo apt update -y && sudo apt install install ffmpeg -y

# Windows (Chocolatey https://chocolatey.org/)
choco install ffmpeg
```

You must also have `uv` package manager installed.

1. Create a virtual environment

```
uv venv .venv
source .venv/bin/activate
```

## Running Tests

The backend test suite uses `pytest` and is organized into:

- `tests/unit` for fast unit coverage around helpers and services
- `tests/integration` for FastAPI, database, and queue-backed API checks
- legacy `unittest`-style tests, which still run under `pytest`

Install dependencies:

```bash
uv sync --all-groups
```

Run the backend suite:

```bash
DATABASE_URL=postgresql+asyncpg://localhost:5432/supoclip \
TEST_DATABASE_URL=postgresql+asyncpg://localhost:5432/supoclip \
REDIS_HOST=127.0.0.1 \
REDIS_PORT=6379 \
.venv/bin/pytest
```

Notes:

- `TEST_DATABASE_URL` should point at a disposable local test database.
- Redis is only required for the integration paths that validate queue and health behavior.
- Coverage thresholds are enforced in `pyproject.toml` during the test run.
- For repo-level entrypoints, use `make test-backend` or `make test-ci` from the repository root.

## Email Configuration

The backend now sends subscription lifecycle emails through Resend.

Set these env vars when using hosted billing:

```
RESEND_API_KEY=your_resend_api_key
RESEND_FROM_EMAIL="KlipOS <onboarding@your-domain.com>"
```

Notes:

- `RESEND_FROM_EMAIL` must be a verified sender/domain in Resend.
- The thank-you email is triggered after a successful Stripe checkout.
- The cancellation email is triggered after Stripe subscription deletion.

## YouTube Downloads

YouTube downloads use `yt-dlp` by default so self-hosted and free deployments do not need Apify.

```env
YOUTUBE_DOWNLOAD_PROVIDER=yt_dlp
```

Set `YOUTUBE_DOWNLOAD_PROVIDER=apify` only when you want to use the paid Apify actor as the primary downloader:

```env
YOUTUBE_DOWNLOAD_PROVIDER=apify
APIFY_API_TOKEN=your_apify_token
APIFY_YOUTUBE_DEFAULT_QUALITY=1080
```

Notes:

- `yt_dlp` is the free default and does not require `APIFY_API_TOKEN`.
- If `yt-dlp` fails and `APIFY_API_TOKEN` is set, the backend can still try Apify as a fallback.
- If Apify is selected but unavailable or fails, the backend falls back to `yt-dlp`.

## YouTube Metadata Provider

Metadata lookup is configurable separately from downloads.

Set these env vars to use the official YouTube Data API v3 for title, duration, channel, thumbnail, and view-count preflight:

```env
YOUTUBE_METADATA_PROVIDER=youtube_data_api
YOUTUBE_DATA_API_KEY=your_youtube_data_api_key
```

Notes:

- `YOUTUBE_METADATA_PROVIDER=yt_dlp` preserves the previous metadata behavior.
- If `YOUTUBE_DATA_API_KEY` is not set, the backend will try `GOOGLE_API_KEY` for YouTube metadata requests.
- The selected metadata provider is the primary path only; the backend automatically falls back to the other provider if the first one fails.
- `videos.list` costs 1 quota unit per request in the YouTube Data API.
- The public API does not expose some `yt-dlp`-specific metadata fields like `format_id`, `resolution`, `fps`, or file size.
- Enable the YouTube Data API v3 for your Google Cloud project before using this mode.

## Vertical clip face framing (9:16 crop)

Clip export uses face-aware centering when `output_format` is `vertical` (see [`video_utils.detect_faces_in_clip`](src/video_utils.py)).

Order of detection:

1. **MediaPipe** — only when the installed wheel still exposes `mediapipe.solutions.face_detection` (some newer PyPI builds omit legacy `solutions`).
2. **OpenCV DNN** — if TensorFlow `.pb` + `.pbtxt` are available.
3. **OpenCV Haar** — fallback; parameters are tuned to reduce false positives.

### Optional: OpenCV DNN weights (recommended for stable framing)

Download the OpenCV sample face detector:

- Model weights: [opencv_face_detector_uint8.pb](https://raw.githubusercontent.com/opencv/opencv_3rdparty/8033c2bc31b3256f0d461c919ecc01c2428ca03b/opencv_face_detector_uint8.pb) (pinned commit from `opencv_3rdparty`)
- Network definition: [opencv_face_detector.pbtxt](https://raw.githubusercontent.com/opencv/opencv/4.x/samples/dnn/face_detector/opencv_face_detector.pbtxt) (from `opencv` samples)

Place them anywhere on disk, then point the worker at them:

```env
OPENCV_FACE_DETECTOR_MODEL_PATH=/absolute/path/to/opencv_face_detector_uint8.pb
OPENCV_FACE_DETECTOR_PROTO_PATH=/absolute/path/to/opencv_face_detector.pbtxt
```

If these are unset, the code still checks the default paths next to OpenCV’s Haar data (they are usually missing in a stock `opencv-python` install, so DNN is skipped until you download the files).

This is unrelated to free vs paid users; framing quality depends on detectors and source video, not billing tier.
