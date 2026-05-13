# AGENTS

Skills are auto-loaded by OpenCode from `.opencode/skills/` (114 skills from `zechenzhangAGI/AI-research-SKILLs`).

## Repo-specific guidance

### Build/train pipeline (order matters)

```
python vocab_built.py    # must run first — generates data/vocab.json, data/label.json
python train.py          # then train — saves best model to data/textcnn_model.pth
                         #   also evaluates on val & test sets at end of training
python evaluate_test.py  # optional — standalone test-set evaluation (use when you
                         #   want to re-evaluate a saved model without retraining)
```

All hyperparameters live in `config.py` — change them there, never inline.

`data/` must exist before running any script (directory is gitignored).

### Incremental training data flow (non-obvious)

When users submit feedback corrections via the web UI, corrected questions land in the `incremental_corpus` DB table as `pending`. An admin must trigger `/api/v1/admin/corpus/flush` to write them to `data/train.txt`. After flushing, re-run `vocab_built.py` → `train.py` to incorporate new data. The model version in DB does **not** auto-update on retrain — admin must register and activate new versions via `/api/v1/admin/models/active`.

### Data format

`config.load_data` splits each line on the first whitespace: `label<TAB or space>text...`. The `Subject_data/*.txt` files use this format. Raw JSON sources are in `Subject_data/*.json`; convert with `Tools/export_json_to_traintxt.py`.

### Run the API server

```
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

The web frontend is served from `web/` via FastAPI `StaticFiles` mount. Login page at `/login`, main app at `/`. Default accounts: `demo_user` / `admin_user` (passwords from env vars below).

### Tests

```
python -m pytest tests/ -v
# or
python -m unittest tests.test_config
```

Tests use `unittest` (not pytest by default, though pytest works). The test reads `data/test1.txt` — ensure file exists (data/ is gitignored).

### API smoke test

```
powershell -ExecutionPolicy Bypass Tools/api_smoke_test.ps1
```

### Architecture notes

- `config.py` — single source of truth for paths, hyperparams, and shared utility functions (`load_data`, `texts_to_indices`, `preprocess_text`, `load_vocab`, `load_labels`)
- `inference.py` — `TextClassifier` class wrapping model load + prediction; used by `app.py` and reusable by scripts
- `model/textcnn_model.py` — TextCNN (Kim 2014): embedding → multi-scale conv (kernel sizes 2/3/4) → BatchNorm → ReLU → max-pool → concat → dropout → FC
- `app.py` — FastAPI app with SQLite (users, questions, feedback, corpus, model versions, sessions). DB auto-created in `data/app.db` on startup. Model loading happens at import time (module-level `TextClassifier.from_files()`), so the server won't start without a trained model.
- `vocab_built.py` builds vocab from training set only (`<PAD>=0`, `<UNK>=1`). Do not include val/test data in vocab to avoid data leakage

### Chinese text processing

Uses `jieba` for word segmentation. The tokenizer assumes Chinese input — do not replace with English-focused tokenizers.

### Environment variables

```
TEXTCNN_DEMO_PASSWORD    (default: demo123456)
TEXTCNN_ADMIN_PASSWORD   (default: admin123456)
TEXTCNN_AI_API_URL       (default: https://api.siliconflow.cn/v1/chat/completions)
TEXTCNN_AI_API_KEY       (default: empty — OCR parse-image/parse-text fail without it)
TEXTCNN_AI_API_MODEL     (default: Qwen/Qwen2.5-VL-72B-Instruct)
```

Legacy `SILICONFLOW_*` env vars also work as fallbacks in `config.py`.

### OCR (optional, not in requirements.txt)

```
pip install rapidocr-onnxruntime opencv-python-headless numpy
```

### Data is gitignored

`data/` and `*.pth`/`*.pt` are in `.gitignore`. Test fixtures and models must be provided locally.

### inference.py vs evaluate_test.py

`inference.py` loads model with `torch.load(..., map_location=self.device)` (no `weights_only`). `evaluate_test.py` uses `weights_only=True`. `train.py` also uses the unsafe default. Do not change one without checking the others.

### API routes

- `/predict` (GET/POST) — legacy compat
- `/api/v1/predict` (POST) — current predict
- `/api/v1/ai/classify` (POST) — returns label + confidence + model_version
- `/api/v1/ocr/recognize`, `/api/v1/ai/parse-image`, `/api/v1/ai/parse-text` — OCR/AI parsing (needs auth + API key)
- `/api/v1/questions` — CRUD (needs auth)
- `/api/v1/auth/login`, `/api/v1/auth/register` — auth
- `/api/v1/ai/feedback` — corrected-label feedback (creates incremental corpus entry)
- `/api/v1/admin/corpus/flush` — writes pending corpus to train.txt (admin only)
- `/api/v1/admin/models/versions`, `/api/v1/admin/models/active` — model version management (admin only)
- `/health`, `/api/v1/labels` — public
