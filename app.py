# -*- coding: utf-8 -*-
"""
后端 API 入口

运行方式：
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

from pathlib import Path
from typing import Any
import json
import sqlite3
import threading
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import DB_PATH, MODEL_VERSION
from inference import TextClassifier


class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待分类文本")


class PredictResponse(BaseModel):
    label: str
    confidence: float


class ClassifyResponse(PredictResponse):
    model_version: str


class CreateQuestionRequest(BaseModel):
    stem: str = Field(..., min_length=1)
    options: list[str] | None = None
    correct_answer: str | None = None
    analysis: str | None = None
    ai_label: str | None = None
    final_label: str = Field(..., min_length=1)
    confidence: float | None = None
    source_type: str = Field(default="manual")


class UpdateStatusRequest(BaseModel):
    to_status: str = Field(..., min_length=1)


class FeedbackRequest(BaseModel):
    question_id: str = Field(..., min_length=1)
    question_text: str = Field(..., min_length=1)
    predicted_label: str = Field(..., min_length=1)
    corrected_label: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)


class UpdateQuestionRequest(BaseModel):
    stem: str | None = None
    analysis: str | None = None
    final_label: str | None = None


class ActivateModelRequest(BaseModel):
    version_name: str = Field(..., min_length=1)


class ApiResponse(BaseModel):
    code: int
    message: str
    data: Any = None


RESPONSES_COMMON = {
    400: {
        "description": "业务参数错误",
        "content": {
            "application/json": {
                "example": {
                    "code": 400,
                    "message": "text 不能为空",
                    "data": None,
                }
            }
        },
    },
    422: {
        "description": "参数校验失败",
        "content": {
            "application/json": {
                "example": {
                    "code": 422,
                    "message": "请求参数校验失败",
                    "data": [
                        {
                            "type": "string_too_short",
                            "loc": ["body", "text"],
                            "msg": "String should have at least 1 character",
                        }
                    ],
                }
            }
        },
    },
    500: {
        "description": "服务器内部错误",
        "content": {
            "application/json": {
                "example": {
                    "code": 500,
                    "message": "服务器内部错误: ...",
                    "data": None,
                }
            }
        },
    },
}


app = FastAPI(title="TextCNN Classification API", version="1.0.0")
api_router = APIRouter(prefix="/api/v1", tags=["v1"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

classifier = TextClassifier()
web_dir = Path("web")

ROLE_SET = {"student", "admin"}
MASTERY_SET = {"unreviewed", "reviewed", "mastered", "careless"}
SOURCE_TYPE_SET = {"manual", "import", "ocr"}
WRITE_STATUS_SET = {"pending", "written", "failed"}
AUTH_TOKEN_USER_MAP = {
    "demo-token": "demo_user",
    "admin-token": "admin_user",
}
LOGIN_USER_TOKEN_MAP = {
    "demo_user": "demo-token",
    "admin_user": "admin-token",
}
CORPUS_FLUSH_LOCK = threading.Lock()
CORPUS_FLUSH_STATE: dict[str, Any] = {
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "processed": 0,
    "written": 0,
    "failed": 0,
    "last_error": None,
}

app.mount("/web", StaticFiles(directory=str(web_dir)), name="web")


def ok(data=None, message="ok"):
    return ApiResponse(code=0, message=message, data=data)


def _utc_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = _connect_db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                stem TEXT NOT NULL,
                options_json TEXT NULL,
                correct_answer TEXT NULL,
                analysis TEXT NULL,
                ai_label TEXT NULL,
                final_label TEXT NOT NULL,
                confidence REAL NULL,
                mastery_status TEXT NOT NULL DEFAULT 'unreviewed',
                source_type TEXT NOT NULL DEFAULT 'manual',
                is_deleted INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_questions_user_created ON questions(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_questions_final_label ON questions(final_label);
            CREATE INDEX IF NOT EXISTS idx_questions_mastery_status ON questions(mastery_status);
            CREATE INDEX IF NOT EXISTS idx_questions_deleted ON questions(is_deleted);

            CREATE TABLE IF NOT EXISTS question_feedback (
                id TEXT PRIMARY KEY,
                question_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                question_text TEXT NOT NULL,
                predicted_label TEXT NOT NULL,
                corrected_label TEXT NOT NULL,
                is_corrected INTEGER NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(question_id) REFERENCES questions(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_feedback_question ON question_feedback(question_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_created ON question_feedback(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_feedback_corrected ON question_feedback(is_corrected);

            CREATE TABLE IF NOT EXISTS incremental_corpus (
                id TEXT PRIMARY KEY,
                question_text TEXT NOT NULL,
                label TEXT NOT NULL,
                source_feedback_id TEXT NOT NULL,
                write_status TEXT NOT NULL DEFAULT 'pending',
                created_at DATETIME NOT NULL,
                FOREIGN KEY(source_feedback_id) REFERENCES question_feedback(id)
            );
            CREATE INDEX IF NOT EXISTS idx_corpus_status ON incremental_corpus(write_status);
            CREATE INDEX IF NOT EXISTS idx_corpus_created ON incremental_corpus(created_at DESC);

            CREATE TABLE IF NOT EXISTS model_versions (
                id TEXT PRIMARY KEY,
                version_name TEXT NOT NULL UNIQUE,
                model_path TEXT NOT NULL,
                notes TEXT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_model_versions_active ON model_versions(is_active);

            CREATE TABLE IF NOT EXISTS question_review_logs (
                id TEXT PRIMARY KEY,
                question_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                from_status TEXT NULL,
                to_status TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(question_id) REFERENCES questions(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_review_question ON question_review_logs(question_id);
            CREATE INDEX IF NOT EXISTS idx_review_user_created ON question_review_logs(user_id, created_at DESC);
            """
        )

        now = _utc_now()
        _ensure_column(conn, "incremental_corpus", "write_error", "TEXT NULL")
        _ensure_column(conn, "incremental_corpus", "written_at", "DATETIME NULL")
        _ensure_column(conn, "incremental_corpus", "updated_at", "DATETIME NULL")

        conn.execute(
            """
            INSERT INTO users(id, username, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at
            """,
            ("demo_user", "demo_user", "student", now, now),
        )
        conn.execute(
            """
            INSERT INTO users(id, username, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at
            """,
            ("admin_user", "admin_user", "admin", now, now),
        )
        conn.execute(
            """
            INSERT INTO model_versions(id, version_name, model_path, notes, is_active, is_deleted, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(version_name) DO UPDATE SET updated_at=excluded.updated_at
            """,
            ("mv_textcnn_v1", MODEL_VERSION, "data/textcnn_model.pth", "default seeded version", 1, 0, now, now),
        )
        active_count = conn.execute(
            "SELECT COUNT(1) AS c FROM model_versions WHERE is_active=1 AND is_deleted=0"
        ).fetchone()["c"]
        if active_count == 0:
            conn.execute(
                "UPDATE model_versions SET is_active=1, updated_at=? WHERE version_name=?",
                (now, MODEL_VERSION),
            )
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl_suffix: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {row["name"] for row in rows}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_suffix}")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse(code=exc.status_code, message=str(exc.detail), data=None).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=ApiResponse(code=422, message="请求参数校验失败", data=exc.errors()).model_dump(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=ApiResponse(code=500, message=f"服务器内部错误: {exc}", data=None).model_dump(),
    )


def _predict_text(text: str):
    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="text 不能为空")

    try:
        return classifier.predict(cleaned)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"预测失败: {exc}") from exc


def _parse_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization 头")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Authorization 格式必须为 Bearer <token>")
    return parts[1].strip()


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = _parse_bearer_token(authorization)
    user_id = AUTH_TOKEN_USER_MAP.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="token 非法或已过期")

    conn = _connect_db()
    try:
        user = conn.execute("SELECT id, username, role FROM users WHERE id=?", (user_id,)).fetchone()
        if user is None:
            raise HTTPException(status_code=401, detail="用户不存在")
        return {"id": user["id"], "username": user["username"], "role": user["role"]}
    finally:
        conn.close()


def get_admin_user(current_user: dict[str, str] = Depends(get_current_user)) -> dict[str, str]:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    return current_user


def _get_active_model_version(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
        SELECT version_name
        FROM model_versions
        WHERE is_active=1 AND is_deleted=0
        ORDER BY updated_at DESC
        LIMIT 1
        """
    ).fetchone()
    return row["version_name"] if row else MODEL_VERSION


def _append_training_line(label: str, question_text: str) -> None:
    clean_text = " ".join(question_text.strip().split())
    if not clean_text:
        raise ValueError("question_text 为空")
    with open("data/train.txt", "a", encoding="utf-8") as f:
        f.write(f"{label} {clean_text}\n")


def _flush_incremental_corpus_job() -> None:
    with CORPUS_FLUSH_LOCK:
        CORPUS_FLUSH_STATE["running"] = True
        CORPUS_FLUSH_STATE["last_started_at"] = _utc_now()
        CORPUS_FLUSH_STATE["last_finished_at"] = None
        CORPUS_FLUSH_STATE["processed"] = 0
        CORPUS_FLUSH_STATE["written"] = 0
        CORPUS_FLUSH_STATE["failed"] = 0
        CORPUS_FLUSH_STATE["last_error"] = None

        conn = _connect_db()
        try:
            rows = conn.execute(
                """
                SELECT id, question_text, label
                FROM incremental_corpus
                WHERE write_status='pending'
                ORDER BY created_at ASC
                """
            ).fetchall()

            now = _utc_now()
            for row in rows:
                CORPUS_FLUSH_STATE["processed"] += 1
                try:
                    _append_training_line(row["label"], row["question_text"])
                    conn.execute(
                        """
                        UPDATE incremental_corpus
                        SET write_status='written', write_error=NULL, written_at=?, updated_at=?
                        WHERE id=?
                        """,
                        (now, now, row["id"]),
                    )
                    CORPUS_FLUSH_STATE["written"] += 1
                except Exception as exc:
                    conn.execute(
                        """
                        UPDATE incremental_corpus
                        SET write_status='failed', write_error=?, updated_at=?
                        WHERE id=?
                        """,
                        (str(exc), now, row["id"]),
                    )
                    CORPUS_FLUSH_STATE["failed"] += 1
            conn.commit()
        except Exception as exc:
            conn.rollback()
            CORPUS_FLUSH_STATE["last_error"] = str(exc)
        finally:
            conn.close()
            CORPUS_FLUSH_STATE["running"] = False
            CORPUS_FLUSH_STATE["last_finished_at"] = _utc_now()


def _validate_label(label: str, field_name: str) -> None:
    if label not in classifier.label2idx:
        raise HTTPException(status_code=400, detail=f"{field_name} 非法: {label}")


def _parse_datetime(param_name: str, value: str | None, end_of_day: bool = False) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{param_name} 时间格式非法") from exc
    if len(value) <= 10:
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59)
        else:
            dt = dt.replace(hour=0, minute=0, second=0)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@app.get("/")
def index_page():
    return FileResponse(web_dir / "index.html")


@app.get(
    "/health",
    response_model=ApiResponse,
    responses={
        200: {
            "description": "健康检查成功",
            "content": {
                "application/json": {
                    "example": {
                        "code": 0,
                        "message": "ok",
                        "data": {"status": "ok"},
                    }
                }
            },
        }
    },
)
def health_check():
    return ok({"status": "ok"})


@api_router.get(
    "/health",
    response_model=ApiResponse,
    responses={
        200: {
            "description": "健康检查成功",
            "content": {
                "application/json": {
                    "example": {
                        "code": 0,
                        "message": "ok",
                        "data": {"status": "ok", "version": "v1"},
                    }
                }
            },
        }
    },
)
def health_check_v1():
    return ok({"status": "ok", "version": "v1"})


@api_router.get(
    "/labels",
    response_model=ApiResponse,
    responses={
        200: {
            "description": "标签列表获取成功",
            "content": {
                "application/json": {
                    "example": {
                        "code": 0,
                        "message": "ok",
                        "data": {
                            "labels": [
                                "computer_architecture",
                                "computer_network",
                                "data_structure",
                                "operating_system",
                            ]
                        },
                    }
                }
            },
        }
    },
)
def list_labels():
    return ok({"labels": sorted(classifier.label2idx.keys())})


@api_router.post("/auth/login", response_model=ApiResponse)
def login(payload: LoginRequest):
    token = LOGIN_USER_TOKEN_MAP.get(payload.username.strip())
    if token is None:
        raise HTTPException(status_code=401, detail="用户名不存在")

    conn = _connect_db()
    try:
        user = conn.execute("SELECT id, role FROM users WHERE id=?", (payload.username.strip(),)).fetchone()
        if user is None:
            raise HTTPException(status_code=401, detail="用户不存在")
    finally:
        conn.close()

    return ok(
        {
            "token_type": "Bearer",
            "access_token": token,
            "user": {"id": payload.username.strip(), "role": user["role"]},
        },
        "登录成功",
    )


@api_router.post(
    "/ai/classify",
    response_model=ApiResponse,
    responses={
        200: {
            "description": "AI 分类成功",
            "content": {
                "application/json": {
                    "example": {
                        "code": 0,
                        "message": "ok",
                        "data": {
                            "label": "operating_system",
                            "confidence": 0.9721,
                            "model_version": "textcnn-v1",
                        },
                    }
                }
            },
        },
        **RESPONSES_COMMON,
    },
)
def classify_v1(payload: PredictRequest):
    result = _predict_text(payload.text)
    conn = _connect_db()
    try:
        model_version = _get_active_model_version(conn)
    finally:
        conn.close()
    return ok(ClassifyResponse(**result, model_version=model_version).model_dump())


@api_router.post("/questions", response_model=ApiResponse)
def create_question(payload: CreateQuestionRequest, current_user: dict[str, str] = Depends(get_current_user)):
    if payload.final_label not in classifier.label2idx:
        raise HTTPException(status_code=400, detail=f"final_label 非法: {payload.final_label}")
    if payload.ai_label:
        _validate_label(payload.ai_label, "ai_label")
    if payload.source_type not in SOURCE_TYPE_SET:
        raise HTTPException(status_code=400, detail=f"source_type 非法: {payload.source_type}")

    question_id = _new_id("q")
    now = _utc_now()
    options_json = json.dumps(payload.options, ensure_ascii=False) if payload.options is not None else None

    conn = _connect_db()
    try:
        user = conn.execute("SELECT id FROM users WHERE id=?", (current_user["id"],)).fetchone()
        if user is None:
            raise HTTPException(status_code=401, detail="登录用户不存在")

        conn.execute(
            """
            INSERT INTO questions(
                id, user_id, stem, options_json, correct_answer, analysis,
                ai_label, final_label, confidence, mastery_status,
                source_type, is_deleted, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                question_id,
                current_user["id"],
                payload.stem,
                options_json,
                payload.correct_answer,
                payload.analysis,
                payload.ai_label,
                payload.final_label,
                payload.confidence,
                "unreviewed",
                payload.source_type,
                0,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return ok({"id": question_id}, "保存成功")


@api_router.get("/questions", response_model=ApiResponse)
def list_questions(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    final_label: str | None = Query(default=None),
    mastery_status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    current_user: dict[str, str] = Depends(get_current_user),
):
    if final_label:
        _validate_label(final_label, "final_label")
    if mastery_status and mastery_status not in MASTERY_SET:
        raise HTTPException(status_code=400, detail=f"mastery_status 非法: {mastery_status}")

    start_dt = _parse_datetime("start_date", start_date)
    end_dt = _parse_datetime("end_date", end_date, end_of_day=True)

    where = ["is_deleted=0", "user_id=?"]
    params: list[Any] = [current_user["id"]]

    if final_label:
        where.append("final_label=?")
        params.append(final_label)
    if mastery_status:
        where.append("mastery_status=?")
        params.append(mastery_status)
    if keyword:
        where.append("stem LIKE ?")
        params.append(f"%{keyword.strip()}%")
    if start_dt:
        where.append("created_at>=?")
        params.append(start_dt)
    if end_dt:
        where.append("created_at<=?")
        params.append(end_dt)

    where_sql = " AND ".join(where)
    offset = (page - 1) * size

    conn = _connect_db()
    try:
        total = conn.execute(f"SELECT COUNT(1) AS c FROM questions WHERE {where_sql}", params).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT id, user_id, stem, options_json, correct_answer, analysis,
                   ai_label, final_label, confidence, mastery_status,
                   source_type, created_at, updated_at
            FROM questions
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, size, offset],
        ).fetchall()
    finally:
        conn.close()

    items = []
    for row in rows:
        options = json.loads(row["options_json"]) if row["options_json"] else None
        items.append(
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "stem": row["stem"],
                "options": options,
                "correct_answer": row["correct_answer"],
                "analysis": row["analysis"],
                "ai_label": row["ai_label"],
                "final_label": row["final_label"],
                "confidence": row["confidence"],
                "mastery_status": row["mastery_status"],
                "source_type": row["source_type"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    return ok({"items": items, "total": total, "page": page, "size": size})


@api_router.get("/questions/{question_id}", response_model=ApiResponse)
def get_question_detail(question_id: str, current_user: dict[str, str] = Depends(get_current_user)):
    conn = _connect_db()
    try:
        row = conn.execute(
            """
            SELECT id, user_id, stem, options_json, correct_answer, analysis,
                   ai_label, final_label, confidence, mastery_status,
                   source_type, is_deleted, created_at, updated_at
            FROM questions
            WHERE id=? AND user_id=? AND is_deleted=0
            """,
            (question_id, current_user["id"]),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    return ok(
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "stem": row["stem"],
            "options": json.loads(row["options_json"]) if row["options_json"] else None,
            "correct_answer": row["correct_answer"],
            "analysis": row["analysis"],
            "ai_label": row["ai_label"],
            "final_label": row["final_label"],
            "confidence": row["confidence"],
            "mastery_status": row["mastery_status"],
            "source_type": row["source_type"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    )


@api_router.patch("/questions/{question_id}", response_model=ApiResponse)
def patch_question(question_id: str, payload: UpdateQuestionRequest, current_user: dict[str, str] = Depends(get_current_user)):
    if payload.final_label is not None:
        _validate_label(payload.final_label, "final_label")

    updates = {}
    if payload.stem is not None:
        stem = payload.stem.strip()
        if not stem:
            raise HTTPException(status_code=400, detail="stem 不能为空")
        updates["stem"] = stem
    if payload.analysis is not None:
        updates["analysis"] = payload.analysis
    if payload.final_label is not None:
        updates["final_label"] = payload.final_label

    if not updates:
        raise HTTPException(status_code=400, detail="至少提供一个可更新字段")

    now = _utc_now()
    updates["updated_at"] = now
    set_sql = ", ".join([f"{k}=?" for k in updates])

    conn = _connect_db()
    try:
        current = conn.execute(
            "SELECT id FROM questions WHERE id=? AND user_id=? AND is_deleted=0",
            (question_id, current_user["id"]),
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="题目不存在")

        conn.execute(
            f"UPDATE questions SET {set_sql} WHERE id=? AND user_id=?",
            [*updates.values(), question_id, current_user["id"]],
        )
        conn.commit()
    finally:
        conn.close()

    return ok({"id": question_id}, "题目更新成功")


@api_router.delete("/questions/{question_id}", response_model=ApiResponse)
def delete_question(question_id: str, current_user: dict[str, str] = Depends(get_current_user)):
    now = _utc_now()
    conn = _connect_db()
    try:
        row = conn.execute(
            "SELECT id FROM questions WHERE id=? AND user_id=? AND is_deleted=0",
            (question_id, current_user["id"]),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="题目不存在")

        conn.execute(
            "UPDATE questions SET is_deleted=1, updated_at=? WHERE id=? AND user_id=?",
            (now, question_id, current_user["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    return ok({"id": question_id}, "题目已删除")


@api_router.patch("/questions/{question_id}/status", response_model=ApiResponse)
def update_question_status(
    question_id: str,
    payload: UpdateStatusRequest,
    current_user: dict[str, str] = Depends(get_current_user),
):
    if payload.to_status not in MASTERY_SET:
        raise HTTPException(status_code=400, detail=f"to_status 非法: {payload.to_status}")

    conn = _connect_db()
    try:
        question = conn.execute(
            "SELECT id, mastery_status FROM questions WHERE id=? AND user_id=? AND is_deleted=0",
            (question_id, current_user["id"]),
        ).fetchone()
        if question is None:
            raise HTTPException(status_code=404, detail="题目不存在")

        now = _utc_now()
        conn.execute("BEGIN")
        conn.execute(
            "UPDATE questions SET mastery_status=?, updated_at=? WHERE id=?",
            (payload.to_status, now, question_id),
        )
        conn.execute(
            """
            INSERT INTO question_review_logs(id, question_id, user_id, from_status, to_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                _new_id("log"),
                question_id,
                current_user["id"],
                question["mastery_status"],
                payload.to_status,
                now,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return ok({"id": question_id, "to_status": payload.to_status}, "状态更新成功")


@api_router.post("/ai/feedback", response_model=ApiResponse)
def create_feedback(payload: FeedbackRequest, current_user: dict[str, str] = Depends(get_current_user)):
    _validate_label(payload.predicted_label, "predicted_label")
    _validate_label(payload.corrected_label, "corrected_label")

    conn = _connect_db()
    try:
        question = conn.execute("SELECT id FROM questions WHERE id=? AND is_deleted=0", (payload.question_id,)).fetchone()
        if question is None:
            raise HTTPException(status_code=404, detail="question_id 不存在")

        now = _utc_now()
        feedback_id = _new_id("fb")
        conn.execute("BEGIN")
        conn.execute(
            """
            INSERT INTO question_feedback(
                id, question_id, user_id, question_text, predicted_label,
                corrected_label, is_corrected, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                payload.question_id,
                current_user["id"],
                payload.question_text,
                payload.predicted_label,
                payload.corrected_label,
                1 if payload.predicted_label != payload.corrected_label else 0,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO incremental_corpus(id, question_text, label, source_feedback_id, write_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                _new_id("corpus"),
                payload.question_text,
                payload.corrected_label,
                feedback_id,
                "pending",
                now,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return ok({"feedback_id": feedback_id}, "反馈已记录")


@api_router.get("/dashboard/subject-distribution", response_model=ApiResponse)
def dashboard_subject_distribution(current_user: dict[str, str] = Depends(get_current_user)):
    conn = _connect_db()
    try:
        rows = conn.execute(
            """
            SELECT final_label, COUNT(1) AS cnt
            FROM questions
            WHERE is_deleted=0 AND user_id=?
            GROUP BY final_label
            ORDER BY cnt DESC
            """,
            (current_user["id"],),
        ).fetchall()
    finally:
        conn.close()

    labels = [row["final_label"] for row in rows]
    counts = [row["cnt"] for row in rows]
    total = sum(counts)
    return ok({"labels": labels, "counts": counts, "total": total})


@api_router.post("/admin/corpus/flush", response_model=ApiResponse)
def trigger_corpus_flush(
    background_tasks: BackgroundTasks,
    _: dict[str, str] = Depends(get_admin_user),
):
    if CORPUS_FLUSH_STATE["running"]:
        return ok({"status": "running"}, "任务正在运行中")
    background_tasks.add_task(_flush_incremental_corpus_job)
    return ok({"status": "started"}, "任务已启动")


@api_router.get("/admin/corpus/flush/status", response_model=ApiResponse)
def corpus_flush_status(_: dict[str, str] = Depends(get_admin_user)):
    return ok(dict(CORPUS_FLUSH_STATE))


@api_router.get("/admin/models/versions", response_model=ApiResponse)
def list_model_versions(_: dict[str, str] = Depends(get_admin_user)):
    conn = _connect_db()
    try:
        rows = conn.execute(
            """
            SELECT id, version_name, model_path, notes, is_active, created_at, updated_at
            FROM model_versions
            WHERE is_deleted=0
            ORDER BY created_at DESC
            """
        ).fetchall()
    finally:
        conn.close()

    return ok(
        {
            "items": [
                {
                    "id": row["id"],
                    "version_name": row["version_name"],
                    "model_path": row["model_path"],
                    "notes": row["notes"],
                    "is_active": bool(row["is_active"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]
        }
    )


@api_router.patch("/admin/models/active", response_model=ApiResponse)
def activate_model(payload: ActivateModelRequest, _: dict[str, str] = Depends(get_admin_user)):
    now = _utc_now()
    conn = _connect_db()
    try:
        target = conn.execute(
            "SELECT id, version_name FROM model_versions WHERE version_name=? AND is_deleted=0",
            (payload.version_name,),
        ).fetchone()
        if target is None:
            raise HTTPException(status_code=404, detail="模型版本不存在")

        conn.execute("BEGIN")
        conn.execute("UPDATE model_versions SET is_active=0, updated_at=? WHERE is_deleted=0", (now,))
        conn.execute(
            "UPDATE model_versions SET is_active=1, updated_at=? WHERE version_name=?",
            (now, payload.version_name),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return ok({"version_name": payload.version_name}, "生效模型已切换")


@api_router.post(
    "/predict",
    response_model=ApiResponse,
    responses={
        200: {
            "description": "预测成功",
            "content": {
                "application/json": {
                    "example": {
                        "code": 0,
                        "message": "ok",
                        "data": {
                            "label": "operating_system",
                            "confidence": 0.9721,
                        },
                    }
                }
            },
        },
        **RESPONSES_COMMON,
    },
)
def predict_v1(payload: PredictRequest):
    result = _predict_text(payload.text)
    return ok(PredictResponse(**result).model_dump())


@app.get(
    "/predict",
    response_model=ApiResponse,
    responses={
        200: {
            "description": "兼容预测接口",
            "content": {
                "application/json": {
                    "example": {
                        "code": 0,
                        "message": "ok",
                        "data": {
                            "label": "operating_system",
                            "confidence": 0.9721,
                        },
                    }
                }
            },
        },
        **RESPONSES_COMMON,
    },
)
def predict_by_query(text: str = Query(default="", description="待分类文本")):
    text = text.strip()
    if not text:
        return ok({
            "message": "建议使用 POST /api/v1/predict 并传 JSON: {\"text\": \"你的问题\"}",
            "example": "/predict?text=链表反转",
            "new_api": "/api/v1/predict",
        }, "请输入 text 查询参数")

    result = _predict_text(text)
    return ok(PredictResponse(**result).model_dump())


@app.post(
    "/predict",
    response_model=ApiResponse,
    responses={
        200: {
            "description": "兼容预测接口",
            "content": {
                "application/json": {
                    "example": {
                        "code": 0,
                        "message": "ok",
                        "data": {
                            "label": "operating_system",
                            "confidence": 0.9721,
                        },
                    }
                }
            },
        },
        **RESPONSES_COMMON,
    },
)
def predict(payload: PredictRequest):
    result = _predict_text(payload.text)
    return ok(PredictResponse(**result).model_dump())


app.include_router(api_router)