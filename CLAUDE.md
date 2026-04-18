# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (Flask, Python)
Run from repo root unless noted. A venv under `backend/venv` is typical.

- Install: `cd backend && pip install -r requirements.txt`
- Run API: `python backend/app.py` — serves on `PORT` env (default **5001**, not 5000 as README says). Frontend `package.json` proxy is pinned to `5000`, so either set `PORT=5000` when running the backend or update the proxy.
- Run all tests: `python -m unittest discover -s backend/tests` (run from repo root — `backend/tests/test_app.py` imports via `from backend import ocr_service`, so the repo root must be on `sys.path`).
- Run one test: `python -m unittest backend.tests.test_app.OCRServiceTests.test_parse_tesseract_tsv_filters_empty_rows_and_normalizes_confidence`

### Frontend (React / CRA)
- Install: `cd frontend && npm install`
- Dev server: `cd frontend && npm start` (port 3000)
- Build: `cd frontend && npm run build`
- Tests: `cd frontend && npm test`

## Architecture

Two-service app: React (CRA) frontend uploads a prescription bottle image to a Flask backend that runs OCR and returns structured text.

### Backend OCR pipeline (`backend/ocr_service.py`)
The critical design point: `extract_text_from_image` is the single entry point and **cascades through multiple OCR engines** rather than hard-depending on any one. Order of attempts:

1. **EasyOCR** on both the preprocessed and original image — `select_better_ocr_result` picks the best by `(text_count, full_text length, avg_confidence)`.
2. If EasyOCR isn't installed → **PaddleOCR** (lazy-loaded via `get_ocr_engine`).
3. If PaddleOCR isn't installed → **Tesseract CLI** (shells out to the `tesseract` binary, parses TSV via `parse_tesseract_tsv`).

All heavy deps (`cv2`, `numpy`, `paddleocr`, `easyocr`) are imported lazily through `get_cv2()` / `get_numpy()` / `get_easyocr_reader()` / `get_ocr_engine()`. **Preserve this laziness** — the unit tests import `backend.ocr_service` in environments without these native deps and stub the engine via the `ocr_engine`, `preprocess_fn`, `save_preprocessed_fn` kwargs of `extract_text_from_image`.

Preprocessing (`preprocess_image`): denoise (fastNlMeansDenoisingColored) → LAB CLAHE contrast enhancement on the L channel. The temp preprocessed file is named via `build_preprocessed_image_path`, which uses `os.path.splitext` specifically to handle multi-dot filenames correctly (covered by a test).

All engine results normalize to the same shape: `{status, full_text, structured_results[{text, confidence, bbox}], text_count, average_confidence, engine}`.

### Backend HTTP layer (`backend/app.py`)
Thin Flask wrapper. Dual import `from backend.ocr_service import …` with fallback to `from ocr_service import …` so the module works whether launched as `python backend/app.py` or as a package. Endpoints: `POST /api/upload`, `POST /api/ocr` (by prior `file_id`), `POST /api/text-extraction` (alias for upload), `GET /health`. Uploads land in `backend/uploads/` with `{timestamp}_{uuid}{ext}` naming; failed OCR deletes the file.

### Frontend (`frontend/src/`)
Single-screen CRA app. `App.jsx` hosts `components/ImageUploader.jsx` which handles drag-drop, preview, and calls the upload endpoint. Uses the `"proxy": "http://localhost:5000"` in `package.json` for dev — no `REACT_APP_API_URL` is required unless deploying.

### Test fixture coupling
`backend/tests/test_app.py::test_real_ocr_on_sample_fixture_captures_key_phrases` asserts that OCR on `docs/image.png` returns specific phrases (e.g. "capture prescription", "symptom > specialist mapping"). This test auto-skips unless a real OCR engine + `cv2` + `numpy` are installed. If you replace `docs/image.png`, update the asserted phrases.

## Notes
- `.env` at repo root is gitignored; `backend/.env.example` is the template (FLASK_ENV, OCR_USE_GPU, CORS_ORIGINS, etc.).
- `flask_cors` is imported defensively — the app runs without it but logs a warning.
- README describes a future pipeline (PubMed research agent, Google Maps specialist finder) that is **not yet implemented**; only OCR exists today.
