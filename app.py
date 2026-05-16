# -*- coding: utf-8 -*-
"""
后端 API 入口

运行方式：
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

from pathlib import Path
from typing import Any
import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import urllib.error
import urllib.request
import uuid
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import ADMIN_PASSWORD, AI_API_KEY, AI_API_MODEL, AI_API_URL, DB_PATH, DEMO_PASSWORD, MODEL_VERSION, TRAIN_PATH
from inference import TextClassifier


class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待分类文本")
    source_type: str = Field(default="manual")


class ParseTextRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待解析题目文本")


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
    knowledge_point: str | None = None
    confidence: float | None = None
    source_type: str = Field(default="manual")


class UpdateStatusRequest(BaseModel):
    to_status: str = Field(..., min_length=1)


class PracticeStartRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=20)


class PracticeSubmitAnswer(BaseModel):
    question_id: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


class PracticeSubmitRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    answers: list[PracticeSubmitAnswer] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    question_id: str = Field(..., min_length=1)
    question_text: str = Field(..., min_length=1)
    predicted_label: str = Field(..., min_length=1)
    corrected_label: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


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

classifier = TextClassifier.from_files()
web_dir = Path(__file__).resolve().parent / "web"

ROLE_SET = {"student", "admin"}
MASTERY_SET = {"unreviewed", "reviewed", "mastered", "careless"}
SOURCE_TYPE_SET = {"manual", "import", "ocr", "practice"}
WRITE_STATUS_SET = {"pending", "written", "failed"}
OCR_KEYWORD_PRIOR: dict[str, tuple[str, ...]] = {
    "computer_network": (
        "tcp", "udp", "ip", "dns", "arp", "http", "https", "osi", "路由", "交换", "网关", "子网", "掩码", "带宽", "吞吐",
    ),
    "data_structure": (
        "链表", "栈", "队列", "数组", "哈希", "二叉树", "红黑树", "堆", "图", "排序", "查找", "dfs", "bfs", "复杂度",
    ),
    "operating_system": (
        "进程", "线程", "死锁", "调度", "虚拟内存", "页面", "页表", "中断", "信号量", "系统调用", "文件系统", "临界区",
    ),
    "computer_architecture": (
        "cpu", "cache", "寄存器", "总线", "流水线", "指令", "寻址", "冯诺依曼", "控制器", "alu", "主存", "中断向量",
    ),
    "xiaosi": (
        "马克思", "毛泽东", "邓小平", "中国特色社会主义", "辩证", "唯物", "社会", "政治", "理论", "思想",
    ),
}
KNOWLEDGE_POINT_MAP: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "data_structure": (
        ("线性表", ("线性", "顺序表", "链表", "单链表", "双链表")),
        ("栈与队列", ("栈", "队列", "栈顶", "队头", "队尾")),
        ("树与二叉树", ("二叉树", "二叉搜索树", "平衡", "红黑树", "堆", "遍历")),
        ("图与遍历", ("图", "邻接", "最短路径", "拓扑", "dfs", "bfs")),
        ("排序与查找", ("排序", "查找", "二分", "快速", "归并", "稳定")),
    ),
    "computer_network": (
        ("传输层", ("tcp", "udp", "拥塞", "三次握手", "四次挥手")),
        ("网络层", ("ip", "子网", "路由", "arp", "icmp")),
        ("应用层", ("http", "https", "dns", "smtp", "ftp")),
        ("数据链路层", ("以太网", "mac", "交换", "帧")),
    ),
    "operating_system": (
        ("进程线程", ("进程", "线程", "pcb", "调度")),
        ("同步互斥", ("死锁", "信号量", "互斥", "临界区", "锁")),
        ("内存管理", ("虚拟内存", "分页", "页表", "缺页", "置换")),
        ("文件系统", ("文件系统", "inode", "磁盘", "目录")),
    ),
    "computer_architecture": (
        ("指令系统", ("指令", "寻址", "流水线")),
        ("存储系统", ("cache", "主存", "高速缓存", "一致性")),
        ("总线与接口", ("总线", "io", "外设")),
    ),
    "xiaosi": (
        ("马克思主义", ("马克思", "唯物", "辩证")),
        ("毛泽东思想", ("毛泽东", "新民主主义", "群众路线")),
        ("中国特色社会主义", ("中国特色社会主义", "改革开放", "现代化")),
    ),
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
OCR_ENGINE: Any | None = None
SUBJECT_DATA_DIR = Path(__file__).resolve().parent / "Subject_data"

PRACTICE_QUESTION_BANK = [
    {
        "id": "pr_001",
        "stem": "在单链表中删除指定节点的时间复杂度通常为？",
        "options": ["A. O(1)", "B. O(log n)", "C. O(n)", "D. O(n log n)"],
        "answer": "C",
        "label": "data_structure",
        "analysis": "需要遍历找到节点或其前驱，平均为 O(n)。",
    },
    {
        "id": "pr_002",
        "stem": "TCP 建立连接采用的握手次数为？",
        "options": ["A. 两次", "B. 三次", "C. 四次", "D. 五次"],
        "answer": "B",
        "label": "computer_network",
        "analysis": "TCP 三次握手用于确认双方收发能力与初始序号。",
    },
    {
        "id": "pr_003",
        "stem": "操作系统中，进程调度的主要目标不包括？",
        "options": ["A. 提高吞吐量", "B. 减少响应时间", "C. 降低电路功耗", "D. 提高CPU利用率"],
        "answer": "C",
        "label": "operating_system",
        "analysis": "调度目标集中于性能与公平性，电路功耗不属于传统调度目标。",
    },
    {
        "id": "pr_004",
        "stem": "下列关于 Cache 的说法正确的是？",
        "options": ["A. Cache 比主存慢", "B. Cache 用于缓冲 CPU 与主存之间的速度差", "C. Cache 只存在于磁盘中", "D. Cache 不需要一致性维护"],
        "answer": "B",
        "label": "computer_architecture",
        "analysis": "Cache 是高速缓存，用于缓解 CPU 与主存速度差。",
    },
    {
        "id": "pr_005",
        "stem": "以下哪种排序算法平均时间复杂度为 O(n log n)？",
        "options": ["A. 冒泡排序", "B. 插入排序", "C. 归并排序", "D. 选择排序"],
        "answer": "C",
        "label": "data_structure",
        "analysis": "归并排序平均/最坏复杂度均为 O(n log n)。",
    },
    {
        "id": "pr_006",
        "stem": "IP 地址属于 OSI 模型的哪一层？",
        "options": ["A. 应用层", "B. 传输层", "C. 网络层", "D. 数据链路层"],
        "answer": "C",
        "label": "computer_network",
        "analysis": "IP 属于网络层协议。",
    },
    {
        "id": "pr_007",
        "stem": "分页系统中，发生缺页时可能触发的操作是？",
        "options": ["A. 中断与页面置换", "B. 进程撤销", "C. 关闭文件系统", "D. 直接跳过"],
        "answer": "A",
        "label": "operating_system",
        "analysis": "缺页触发中断，若内存不足需要页面置换。",
    },
    {
        "id": "pr_008",
        "stem": "指令流水线可以提高 CPU 的什么指标？",
        "options": ["A. 指令吞吐率", "B. 单条指令延迟", "C. 主频", "D. 缓存命中率"],
        "answer": "A",
        "label": "computer_architecture",
        "analysis": "流水线提升单位时间完成指令数。",
    },
    {
        "id": "pr_009",
        "stem": "马克思主义认为社会发展的根本动力是？",
        "options": ["A. 经济危机", "B. 阶级斗争", "C. 科学技术", "D. 政党斗争"],
        "answer": "B",
        "label": "xiaosi",
        "analysis": "历史唯物主义强调阶级斗争推动社会变革。",
    },
    {
        "id": "pr_010",
        "stem": "队列中元素的进出规则是？",
        "options": ["A. 后进先出", "B. 随机", "C. 先进先出", "D. 优先级"],
        "answer": "C",
        "label": "data_structure",
        "analysis": "队列遵循 FIFO。",
    },
]

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


def _hash_password(password: str, salt: str | None = None) -> str:
    if salt is None:
        salt = os.urandom(16).hex()
    iterations = 120000
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${pwd_hash}"


def _normalize_stem(text: str) -> str:
    return " ".join(text.strip().split())


def _stem_hash(text: str) -> str:
    normalized = _normalize_stem(text).lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _infer_knowledge_point(text: str, label: str) -> str:
    text_lower = (text or "").lower()
    rules = KNOWLEDGE_POINT_MAP.get(label, ())
    best_point = "未归类"
    best_score = 0
    for point, keywords in rules:
        score = 0
        for kw in keywords:
            if kw and kw in text_lower:
                score += 1
        if score > best_score:
            best_score = score
            best_point = point
    return best_point


def _format_options_from_dict(options: dict[str, Any] | None) -> list[str]:
    if not options:
        return []
    formatted: list[str] = []
    for key in ("A", "B", "C", "D"):
        if key not in options:
            continue
        value = str(options[key]).replace("\n", " ").strip()
        if not value:
            continue
        formatted.append(f"{key}. {value}")
    return formatted


def _verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algo, iter_s, salt, expected = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        calculated = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iter_s),
        ).hex()
        return hmac.compare_digest(calculated, expected)
    except Exception:
        return False


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
                knowledge_point TEXT NULL,
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

            CREATE TABLE IF NOT EXISTS user_sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                expired_at DATETIME NULL,
                is_revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_sessions_revoked ON user_sessions(is_revoked);

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

            CREATE TABLE IF NOT EXISTS question_bank (
                id TEXT PRIMARY KEY,
                stem_hash TEXT NOT NULL UNIQUE,
                stem TEXT NOT NULL,
                label TEXT NOT NULL,
                knowledge_point TEXT NULL,
                options_json TEXT NULL,
                correct_answer TEXT NULL,
                analysis TEXT NULL,
                source_type TEXT NOT NULL DEFAULT 'import',
                source_user_id TEXT NULL,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_question_bank_label ON question_bank(label);
            CREATE INDEX IF NOT EXISTS idx_question_bank_knowledge ON question_bank(knowledge_point);
            CREATE INDEX IF NOT EXISTS idx_question_bank_deleted ON question_bank(is_deleted);

            CREATE TABLE IF NOT EXISTS practice_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                total_count INTEGER NOT NULL,
                correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                completed_at DATETIME NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_practice_sessions_user_created ON practice_sessions(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS practice_items (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                stem TEXT NOT NULL,
                options_json TEXT NULL,
                correct_answer TEXT NOT NULL,
                label TEXT NOT NULL,
                knowledge_point TEXT NULL,
                analysis TEXT NULL,
                user_answer TEXT NULL,
                is_correct INTEGER NOT NULL DEFAULT 0,
                answered_at DATETIME NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(session_id) REFERENCES practice_sessions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_practice_items_session ON practice_items(session_id);
            CREATE INDEX IF NOT EXISTS idx_practice_items_answered ON practice_items(is_correct, answered_at DESC);
            """
        )

        now = _utc_now()
        _ensure_column(conn, "incremental_corpus", "write_error", "TEXT NULL")
        _ensure_column(conn, "incremental_corpus", "written_at", "DATETIME NULL")
        _ensure_column(conn, "incremental_corpus", "updated_at", "DATETIME NULL")
        _ensure_column(conn, "questions", "knowledge_point", "TEXT NULL")
        _ensure_column(conn, "practice_items", "knowledge_point", "TEXT NULL")

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
        demo_hash = _hash_password(DEMO_PASSWORD)
        admin_hash = _hash_password(ADMIN_PASSWORD)
        conn.execute("UPDATE users SET password_hash=?, updated_at=? WHERE id='demo_user' AND (password_hash IS NULL OR password_hash='')", (demo_hash, now))
        conn.execute("UPDATE users SET password_hash=?, updated_at=? WHERE id='admin_user' AND (password_hash IS NULL OR password_hash='')", (admin_hash, now))
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


def _upsert_question_bank(
    conn: sqlite3.Connection,
    stem: str,
    label: str,
    knowledge_point: str | None,
    options_json: str | None,
    correct_answer: str | None,
    analysis: str | None,
    source_type: str,
    source_user_id: str | None,
) -> None:
    stem_norm = _normalize_stem(stem)
    if not stem_norm:
        return
    now = _utc_now()
    stem_hash = _stem_hash(stem_norm)
    conn.execute(
        """
        INSERT INTO question_bank(
            id, stem_hash, stem, label, knowledge_point, options_json,
            correct_answer, analysis, source_type, source_user_id,
            is_deleted, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        ON CONFLICT(stem_hash) DO UPDATE SET
            label=excluded.label,
            knowledge_point=excluded.knowledge_point,
            options_json=COALESCE(question_bank.options_json, excluded.options_json),
            correct_answer=COALESCE(question_bank.correct_answer, excluded.correct_answer),
            analysis=COALESCE(question_bank.analysis, excluded.analysis),
            updated_at=excluded.updated_at
        """,
        (
            _new_id("qb"),
            stem_hash,
            stem_norm,
            label,
            knowledge_point,
            options_json,
            correct_answer,
            analysis,
            source_type,
            source_user_id,
            now,
            now,
        ),
    )


def _sync_question_bank_from_files() -> None:
    if not SUBJECT_DATA_DIR.exists():
        return

    conn = _connect_db()
    try:
        for json_path in SUBJECT_DATA_DIR.glob("*.json"):
            label = json_path.stem
            if label not in classifier.label2idx:
                continue
            try:
                with json_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            for item in data if isinstance(data, list) else []:
                stem = str(item.get("question") or item.get("stem") or "").replace("\n", " ").strip()
                if not stem:
                    continue
                options_list = _format_options_from_dict(item.get("options") if isinstance(item, dict) else None)
                options_json = json.dumps(options_list, ensure_ascii=False) if options_list else None
                answer = str(item.get("answer") or "").strip().upper()
                if answer not in ("A", "B", "C", "D"):
                    answer = ""
                knowledge_point = _infer_knowledge_point(stem, label)
                _upsert_question_bank(
                    conn,
                    stem=stem,
                    label=label,
                    knowledge_point=knowledge_point,
                    options_json=options_json,
                    correct_answer=answer or None,
                    analysis=None,
                    source_type="import",
                    source_user_id=None,
                )

        for txt_path in SUBJECT_DATA_DIR.glob("*.txt"):
            with txt_path.open("r", encoding="utf-8") as f:
                for line in f:
                    raw = line.strip()
                    if not raw:
                        continue
                    if " " not in raw and "\t" not in raw:
                        continue
                    label, stem = raw.split(maxsplit=1)
                    if not stem:
                        continue
                    if label not in classifier.label2idx:
                        continue
                    knowledge_point = _infer_knowledge_point(stem, label)
                    _upsert_question_bank(
                        conn,
                        stem=stem,
                        label=label,
                        knowledge_point=knowledge_point,
                        options_json=None,
                        correct_answer=None,
                        analysis=None,
                        source_type="import",
                        source_user_id=None,
                    )
        conn.commit()
    finally:
        conn.close()


def _get_weak_knowledge_points(conn: sqlite3.Connection, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            final_label,
            COALESCE(knowledge_point, '未归类') AS kp,
            COUNT(1) AS total_cnt,
            SUM(CASE WHEN mastery_status IN ('unreviewed', 'careless') THEN 1 ELSE 0 END) AS weak_cnt
        FROM questions
        WHERE is_deleted=0 AND user_id=?
        GROUP BY final_label, kp
        HAVING total_cnt > 0
        ORDER BY weak_cnt DESC, total_cnt DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [
        {
            "label": row["final_label"],
            "knowledge_point": row["kp"],
            "total_cnt": int(row["total_cnt"] or 0),
            "weak_cnt": int(row["weak_cnt"] or 0),
            "weak_rate": round((row["weak_cnt"] or 0) / (row["total_cnt"] or 1), 4),
        }
        for row in rows
    ]


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    _sync_question_bank_from_files()


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


def _normalize_text_for_classify(text: str, source_type: str = "manual") -> str:
    cleaned = " ".join(text.strip().split())
    if source_type != "ocr":
        return cleaned

    cleaned = cleaned.lower()
    cleaned = re.sub(r"[\r\n\t]+", " ", cleaned)
    cleaned = re.sub(r"[|丨_~`]+", " ", cleaned)
    cleaned = re.sub(r"\b[a-d]\s*[\.\):：]", " ", cleaned)
    cleaned = re.sub(r"[^0-9a-z\u4e00-\u9fff\s]", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _keyword_prior_for_ocr(text: str) -> dict[str, float]:
    hit_count: dict[str, int] = {label: 0 for label in classifier.label2idx.keys()}
    for label, keywords in OCR_KEYWORD_PRIOR.items():
        if label not in hit_count:
            continue
        count = 0
        for kw in keywords:
            if kw and kw in text:
                count += 1
        hit_count[label] = count

    total = sum(hit_count.values())
    if total == 0:
        return {label: 0.0 for label in hit_count.keys()}
    return {label: hit_count[label] / total for label in hit_count.keys()}


def _predict_text(text: str, source_type: str = "manual"):
    cleaned = _normalize_text_for_classify(text, source_type)
    if not cleaned:
        raise HTTPException(status_code=400, detail="text 不能为空")

    try:
        model_scores = classifier.predict_proba(cleaned)
        if source_type == "ocr":
            prior_scores = _keyword_prior_for_ocr(cleaned)
            top_model_conf = max(model_scores.values()) if model_scores else 0.0
            alpha = 0.85 if top_model_conf >= 0.7 else 0.65
            fused_scores = {
                label: alpha * model_scores.get(label, 0.0) + (1 - alpha) * prior_scores.get(label, 0.0)
                for label in classifier.label2idx.keys()
            }
            label, confidence = max(fused_scores.items(), key=lambda x: x[1])
            return {"label": label, "confidence": float(confidence)}

        label, confidence = max(model_scores.items(), key=lambda x: x[1])
        return {"label": label, "confidence": float(confidence)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"预测失败: {exc}") from exc


def _get_ocr_engine() -> Any:
    global OCR_ENGINE
    if OCR_ENGINE is not None:
        return OCR_ENGINE

    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"OCR 组件未安装或初始化失败: {exc}",
        ) from exc

    OCR_ENGINE = RapidOCR()
    return OCR_ENGINE


def _ocr_extract_text(image_bytes: bytes) -> str:
    if not image_bytes:
        raise HTTPException(status_code=400, detail="上传图片为空")

    try:
        import cv2
        import numpy as np
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"OCR 运行依赖缺失: {exc}") from exc

    np_buf = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_buf, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="图片解码失败，请检查文件格式")

    engine = _get_ocr_engine()
    result, _ = engine(image)
    if not result:
        return ""

    lines: list[str] = []
    for item in result:
        if len(item) < 2:
            continue
        text_part = str(item[1]).strip()
        if text_part:
            lines.append(text_part)

    return "\n".join(lines).strip()


def _build_local_ocr_analysis(ocr_text: str, label: str, confidence: float) -> str:
    preview = ocr_text.strip().replace("\n", " ")[:160]
    confidence_percent = (confidence or 0.0) * 100
    return (
        "参考解析：\n"
        f"题干要点：{preview}\n"
        f"学科判断：{label}（置信度 {confidence_percent:.2f}%）\n"
        "请结合课程知识点核对最终答案。"
    )


def _strip_markdown_symbols(text: str) -> str:
    if not text:
        return ""

    cleaned = text
    cleaned = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).replace("```", ""), cleaned)
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
    cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
    cleaned = re.sub(r"_(.*?)_", r"\1", cleaned)
    cleaned = re.sub(r"^\s*>\s?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-+*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _format_answer_analysis(text: str) -> str:
    cleaned = _strip_markdown_symbols(text)
    if not cleaned:
        return ""

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    answer = ""
    analysis = ""

    answer_match = re.search(r"(?:^|\n)\s*答案\s*[：:]\s*(.+)", cleaned)
    analysis_match = re.search(r"(?:^|\n)\s*解析\s*[：:]\s*([\s\S]+)$", cleaned)

    if answer_match:
        answer = answer_match.group(1).strip()
    if analysis_match:
        analysis = analysis_match.group(1).strip()

    if not answer and lines:
        answer = lines[0]
    if not analysis:
        if answer and len(lines) > 1:
            analysis = "\n".join(lines[1:]).strip()
        else:
            analysis = cleaned

    if not answer:
        answer = "未能从题图中提取明确答案"
    if not analysis:
        analysis = "未能提取有效解析，请结合原题核对。"

    return f"答案：{answer}\n\n解析：{analysis}"


def _call_external_ai_parse(image_bytes: bytes, content_type: str | None, ocr_text: str) -> str | None:
    api_key = (AI_API_KEY or "").strip()
    model = (AI_API_MODEL or "Qwen/Qwen2.5-VL-72B-Instruct").strip()
    if not api_key:
        return None

    api_url = (AI_API_URL or "").strip()
    if not api_url:
        api_url = "https://api.siliconflow.cn/v1/chat/completions"

    mime = content_type if content_type and content_type.startswith("image/") else "image/png"
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是考研408智能助教。请严格按以下格式输出：\n答案：<一句话结论>\n\n解析：<分点或短段落解释>\n不要输出任何其他标题或前后缀。",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "请根据题目图片给出最终答案和简洁解析。"
                            "若图片不清晰，请结合以下OCR文本进行判断：\n"
                            f"{ocr_text}"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{image_b64}",
                        },
                    },
                ],
            },
        ],
        "temperature": 0.2,
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"外部AI解析服务调用失败: {exc}") from exc

    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise HTTPException(status_code=502, detail="外部AI解析服务返回格式异常") from exc

    if isinstance(content, list):
        text_items = [item.get("text", "") for item in content if isinstance(item, dict)]
        merged = "\n".join([t.strip() for t in text_items if t and t.strip()]).strip()
        formatted = _format_answer_analysis(merged)
        return formatted or None

    formatted = _format_answer_analysis(str(content).strip())
    return formatted or None


def _call_external_ai_parse_text(question_text: str) -> str | None:
    api_key = (AI_API_KEY or "").strip()
    model = (AI_API_MODEL or "Qwen/Qwen2.5-VL-72B-Instruct").strip()
    if not api_key:
        return None

    api_url = (AI_API_URL or "").strip()
    if not api_url:
        api_url = "https://api.siliconflow.cn/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是考研408智能助教。请严格按以下格式输出：\n答案：<一句话结论>\n\n解析：<分点或短段落解释>\n不要输出任何其他标题或前后缀。",
            },
            {
                "role": "user",
                "content": f"请根据以下题目文本给出最终答案和简洁解析：\n{question_text}",
            },
        ],
        "temperature": 0.2,
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"外部AI解析服务调用失败: {exc}") from exc

    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise HTTPException(status_code=502, detail="外部AI解析服务返回格式异常") from exc

    if isinstance(content, list):
        text_items = [item.get("text", "") for item in content if isinstance(item, dict)]
        merged = "\n".join([t.strip() for t in text_items if t and t.strip()]).strip()
        formatted = _format_answer_analysis(merged)
        return formatted or None

    formatted = _format_answer_analysis(str(content).strip())
    return formatted or None


def _call_external_ai_judge(question_text: str, options: list[str] | None, user_answer: str) -> bool | None:
    api_key = (AI_API_KEY or "").strip()
    model = (AI_API_MODEL or "Qwen/Qwen2.5-VL-72B-Instruct").strip()
    if not api_key:
        return None

    api_url = (AI_API_URL or "").strip()
    if not api_url:
        api_url = "https://api.siliconflow.cn/v1/chat/completions"

    option_text = "\n".join(options or [])
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是判题助手。只输出 CORRECT 或 INCORRECT，不要输出其他内容。",
            },
            {
                "role": "user",
                "content": (
                    "题目：\n"
                    f"{question_text}\n\n"
                    "选项：\n"
                    f"{option_text}\n\n"
                    "用户答案：\n"
                    f"{user_answer}\n\n"
                    "判断是否正确。"
                ),
            },
        ],
        "temperature": 0.0,
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"外部AI判题服务调用失败: {exc}") from exc

    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise HTTPException(status_code=502, detail="外部AI判题服务返回格式异常") from exc

    result = str(content).strip().upper()
    if "CORRECT" in result and "INCORRECT" not in result:
        return True
    if "INCORRECT" in result:
        return False
    return None


def _parse_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization 头")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Authorization 格式必须为 Bearer <token>")
    return parts[1].strip()


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = _parse_bearer_token(authorization)

    conn = _connect_db()
    try:
        user = conn.execute(
            """
            SELECT u.id, u.username, u.role
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token=?
              AND s.is_revoked=0
              AND (s.expired_at IS NULL OR datetime(s.expired_at) > datetime('now'))
            LIMIT 1
            """,
            (token,),
        ).fetchone()
        if user is None:
            raise HTTPException(status_code=401, detail="token 非法或已过期")
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
    with open(TRAIN_PATH, "a", encoding="utf-8") as f:
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


def _pick_practice_questions(conn: sqlite3.Connection, user_id: str, count: int) -> list[dict[str, Any]]:
    if count <= 0:
        raise HTTPException(status_code=400, detail="count 必须大于 0")

    weak_items = _get_weak_knowledge_points(conn, user_id, limit=8)
    weak_points = [item["knowledge_point"] for item in weak_items if item["knowledge_point"]]

    items: list[sqlite3.Row] = []
    if weak_points:
        placeholders = ",".join(["?"] * len(weak_points))
        rows = conn.execute(
            f"""
            SELECT id, stem, label, knowledge_point, options_json, correct_answer, analysis
            FROM question_bank
            WHERE is_deleted=0 AND knowledge_point IN ({placeholders}) AND options_json IS NOT NULL
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (*weak_points, count),
        ).fetchall()
        items.extend(rows)

    remaining = count - len(items)
    if remaining > 0:
        rows = conn.execute(
            """
            SELECT id, stem, label, knowledge_point, options_json, correct_answer, analysis
            FROM question_bank
            WHERE is_deleted=0 AND options_json IS NOT NULL
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (remaining,),
        ).fetchall()
        items.extend(rows)

    if not items:
        pool = PRACTICE_QUESTION_BANK
        if not pool:
            raise HTTPException(status_code=500, detail="练习题库为空")
        if count >= len(pool):
            random.shuffle(pool)
            picked = pool[:count]
        else:
            picked = random.sample(pool, count)
        for item in picked:
            if not item.get("knowledge_point"):
                item["knowledge_point"] = _infer_knowledge_point(item.get("stem", ""), item.get("label", ""))
        return picked

    results: list[dict[str, Any]] = []
    for row in items[:count]:
        options = json.loads(row["options_json"]) if row["options_json"] else []
        results.append(
            {
                "id": row["id"],
                "stem": row["stem"],
                "options": options,
                "answer": row["correct_answer"] or "",
                "label": row["label"],
                "knowledge_point": row["knowledge_point"] or "未归类",
                "analysis": row["analysis"],
            }
        )
    return results


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


@app.get("/login")
def login_page():
    return FileResponse(web_dir / "login.html")


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
    username = payload.username.strip()

    conn = _connect_db()
    try:
        user = conn.execute(
            "SELECT id, username, role, password_hash FROM users WHERE username=?",
            (username,),
        ).fetchone()
        if user is None:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if not _verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        now = _utc_now()
        token = _new_id("tk")
        expired_at = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO user_sessions(token, user_id, created_at, expired_at, is_revoked) VALUES (?, ?, ?, ?, 0)",
            (token, user["id"], now, expired_at),
        )
        conn.commit()
    finally:
        conn.close()

    return ok(
        {
            "token_type": "Bearer",
            "access_token": token,
            "expires_in_days": 30,
            "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
        },
        "登录成功",
    )


@api_router.post("/auth/register", response_model=ApiResponse)
def register(payload: RegisterRequest):
    username = payload.username.strip()
    if not username.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="用户名仅支持字母、数字、下划线")

    now = _utc_now()
    user_id = username
    password_hash = _hash_password(payload.password)

    conn = _connect_db()
    try:
        exists = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if exists is not None:
            raise HTTPException(status_code=400, detail="用户名已存在")

        conn.execute(
            "INSERT INTO users(id, username, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, password_hash, "student", now, now),
        )
        conn.commit()
    finally:
        conn.close()

    return ok({"id": user_id, "username": username, "role": "student"}, "注册成功")


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
    source_type = payload.source_type.strip().lower() if payload.source_type else "manual"
    if source_type not in SOURCE_TYPE_SET:
        raise HTTPException(status_code=400, detail=f"source_type 非法: {source_type}")

    result = _predict_text(payload.text, source_type=source_type)
    conn = _connect_db()
    try:
        model_version = _get_active_model_version(conn)
    finally:
        conn.close()
    return ok(ClassifyResponse(**result, model_version=model_version).model_dump())


@api_router.post("/ocr/recognize", response_model=ApiResponse)
async def ocr_recognize(file: UploadFile = File(...), _: dict[str, str] = Depends(get_current_user)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")

    text = _ocr_extract_text(image_bytes)
    if not text:
        raise HTTPException(status_code=400, detail="未识别到可用文本")

    return ok(
        {
            "text": text,
            "filename": file.filename,
            "source_type": "ocr",
        },
        "图片识别成功",
    )


@api_router.post("/ai/parse-image", response_model=ApiResponse)
async def parse_image_by_ai(file: UploadFile = File(...), _: dict[str, str] = Depends(get_current_user)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")

    text = _ocr_extract_text(image_bytes)
    if not text:
        raise HTTPException(status_code=400, detail="未识别到可用文本")

    if not (AI_API_KEY or "").strip():
        raise HTTPException(status_code=503, detail="未配置外部解析API密钥，请先设置 SILICONFLOW_API_KEY")

    pred = _predict_text(text, source_type="ocr")
    external_analysis = _call_external_ai_parse(image_bytes, file.content_type, text)
    if not external_analysis:
        raise HTTPException(status_code=502, detail="外部解析API未返回有效内容")

    return ok(
        {
            "analysis": external_analysis,
            "ocr_text": text,
            "label": pred["label"],
            "confidence": pred["confidence"],
            "provider": "external_ai",
        },
        "图片解析成功",
    )


@api_router.post("/ai/parse-text", response_model=ApiResponse)
def parse_text_by_ai(payload: ParseTextRequest, _: dict[str, str] = Depends(get_current_user)):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="题目文本不能为空")

    if not (AI_API_KEY or "").strip():
        raise HTTPException(status_code=503, detail="未配置外部解析API密钥，请先设置 SILICONFLOW_API_KEY")

    pred = _predict_text(text, source_type="manual")
    external_analysis = _call_external_ai_parse_text(text)
    if not external_analysis:
        raise HTTPException(status_code=502, detail="外部解析API未返回有效内容")

    return ok(
        {
            "analysis": external_analysis,
            "label": pred["label"],
            "confidence": pred["confidence"],
            "provider": "external_ai",
        },
        "文本解析成功",
    )


@api_router.post("/practice/start", response_model=ApiResponse)
def start_practice(payload: PracticeStartRequest, current_user: dict[str, str] = Depends(get_current_user)):
    count = int(payload.count)
    session_id = _new_id("ps")
    now = _utc_now()

    conn = _connect_db()
    try:
        questions = _pick_practice_questions(conn, current_user["id"], count)
        conn.execute(
            """
            INSERT INTO practice_sessions(id, user_id, total_count, correct_count, wrong_count, created_at, completed_at)
            VALUES (?, ?, ?, 0, 0, ?, NULL)
            """,
            (session_id, current_user["id"], len(questions), now),
        )

        for item in questions:
            _validate_label(item["label"], "label")
            options_json = json.dumps(item.get("options"), ensure_ascii=False) if item.get("options") else None
            correct_answer = item.get("answer") or ""
            conn.execute(
                """
                INSERT INTO practice_items(
                    id, session_id, question_id, stem, options_json, correct_answer,
                    label, knowledge_point, analysis, user_answer, is_correct, answered_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL, ?)
                """,
                (
                    _new_id("pi"),
                    session_id,
                    item["id"],
                    item["stem"],
                    options_json,
                    correct_answer,
                    item["label"],
                    item.get("knowledge_point"),
                    item.get("analysis"),
                    now,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    return ok(
        {
            "session_id": session_id,
            "questions": [
                {
                    "id": item["id"],
                    "stem": item["stem"],
                    "options": item.get("options") or [],
                    "label": item.get("label"),
                    "knowledge_point": item.get("knowledge_point") or "未归类",
                }
                for item in questions
            ],
            "total": len(questions),
        },
        "练习已开始",
    )


@api_router.post("/practice/submit", response_model=ApiResponse)
def submit_practice(payload: PracticeSubmitRequest, current_user: dict[str, str] = Depends(get_current_user)):
    if not payload.answers:
        raise HTTPException(status_code=400, detail="answers 不能为空")

    conn = _connect_db()
    try:
        session = conn.execute(
            "SELECT id, completed_at FROM practice_sessions WHERE id=? AND user_id=?",
            (payload.session_id, current_user["id"]),
        ).fetchone()
        if session is None:
            raise HTTPException(status_code=404, detail="练习记录不存在")
        if session["completed_at"]:
            raise HTTPException(status_code=400, detail="该练习已提交")

        items = conn.execute(
            "SELECT * FROM practice_items WHERE session_id=?",
            (payload.session_id,),
        ).fetchall()
        if not items:
            raise HTTPException(status_code=400, detail="练习题目为空")

        answer_map = {item.question_id: item.answer.strip() for item in payload.answers if item.answer}
        if len(answer_map) < len(items):
            raise HTTPException(status_code=400, detail="请完成所有题目后再提交")

        now = _utc_now()
        correct_count = 0
        wrong_items: list[dict[str, Any]] = []

        for item in items:
            qid = item["question_id"]
            user_answer = answer_map.get(qid, "")
            options = json.loads(item["options_json"]) if item["options_json"] else []
            if not item["correct_answer"]:
                raise HTTPException(status_code=400, detail="题库缺少正确答案，无法判题")
            is_correct = 1 if user_answer == item["correct_answer"] else 0
            if is_correct:
                correct_count += 1
            else:
                wrong_items.append(
                    {
                        "stem": item["stem"],
                        "label": item["label"],
                        "knowledge_point": item["knowledge_point"],
                        "correct_answer": item["correct_answer"],
                        "user_answer": user_answer,
                        "analysis": item["analysis"],
                        "options_json": item["options_json"],
                    }
                )

            conn.execute(
                """
                UPDATE practice_items
                SET user_answer=?, is_correct=?, answered_at=?
                WHERE id=?
                """,
                (user_answer, is_correct, now, item["id"]),
            )

        wrong_count = len(items) - correct_count
        conn.execute(
            """
            UPDATE practice_sessions
            SET correct_count=?, wrong_count=?, completed_at=?
            WHERE id=?
            """,
            (correct_count, wrong_count, now, payload.session_id),
        )

        for item in wrong_items:
            question_id = _new_id("q")
            conn.execute(
                """
                INSERT INTO questions(
                    id, user_id, stem, options_json, correct_answer, analysis,
                    ai_label, final_label, knowledge_point, confidence, mastery_status,
                    source_type, is_deleted, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question_id,
                    current_user["id"],
                    item["stem"],
                    item.get("options_json"),
                    item["correct_answer"],
                    item["analysis"],
                    None,
                    item["label"],
                    item.get("knowledge_point"),
                    None,
                    "unreviewed",
                    "practice",
                    0,
                    now,
                    now,
                ),
            )

        conn.commit()
    finally:
        conn.close()

    total = len(items)
    accuracy = (correct_count / total) if total else 0.0
    return ok(
        {
            "session_id": payload.session_id,
            "total": total,
            "correct": correct_count,
            "wrong": total - correct_count,
            "accuracy": accuracy,
            "wrong_questions": wrong_items,
        },
        "练习提交成功",
    )


@api_router.get("/practice/history", response_model=ApiResponse)
def practice_history(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: dict[str, str] = Depends(get_current_user),
):
    conn = _connect_db()
    try:
        rows = conn.execute(
            """
            SELECT id, total_count, correct_count, wrong_count, created_at, completed_at
            FROM practice_sessions
            WHERE user_id=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (current_user["id"], limit),
        ).fetchall()
    finally:
        conn.close()

    items = [
        {
            "id": row["id"],
            "total": row["total_count"],
            "correct": row["correct_count"],
            "wrong": row["wrong_count"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }
        for row in rows
    ]
    return ok({"items": items}, "获取成功")


@api_router.get("/practice/history/{session_id}", response_model=ApiResponse)
def practice_history_detail(session_id: str, current_user: dict[str, str] = Depends(get_current_user)):
    conn = _connect_db()
    try:
        session = conn.execute(
            """
            SELECT id, total_count, correct_count, wrong_count, created_at, completed_at
            FROM practice_sessions
            WHERE id=? AND user_id=?
            """,
            (session_id, current_user["id"]),
        ).fetchone()
        if session is None:
            raise HTTPException(status_code=404, detail="练习记录不存在")

        items = conn.execute(
            """
            SELECT question_id, stem, options_json, correct_answer, label, knowledge_point, analysis, user_answer, is_correct
            FROM practice_items
            WHERE session_id=?
            ORDER BY created_at ASC
            """,
            (session_id,),
        ).fetchall()
    finally:
        conn.close()

    return ok(
        {
            "session": {
                "id": session["id"],
                "total": session["total_count"],
                "correct": session["correct_count"],
                "wrong": session["wrong_count"],
                "created_at": session["created_at"],
                "completed_at": session["completed_at"],
            },
            "items": [
                {
                    "id": row["question_id"],
                    "stem": row["stem"],
                    "options": json.loads(row["options_json"]) if row["options_json"] else [],
                    "correct_answer": row["correct_answer"],
                    "label": row["label"],
                    "knowledge_point": row["knowledge_point"] or "未归类",
                    "analysis": row["analysis"],
                    "user_answer": row["user_answer"],
                    "is_correct": bool(row["is_correct"]),
                    "answer_mode": "choice" if row["options_json"] and row["correct_answer"] else "self",
                }
                for row in items
            ],
        },
        "获取成功",
    )


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
    knowledge_point = payload.knowledge_point or _infer_knowledge_point(payload.stem, payload.final_label)

    conn = _connect_db()
    try:
        user = conn.execute("SELECT id FROM users WHERE id=?", (current_user["id"],)).fetchone()
        if user is None:
            raise HTTPException(status_code=401, detail="登录用户不存在")

        conn.execute(
            """
            INSERT INTO questions(
                id, user_id, stem, options_json, correct_answer, analysis,
                ai_label, final_label, knowledge_point, confidence, mastery_status,
                source_type, is_deleted, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                knowledge_point,
                payload.confidence,
                "unreviewed",
                payload.source_type,
                0,
                now,
                now,
            ),
        )
        _upsert_question_bank(
            conn,
            stem=payload.stem,
            label=payload.final_label,
            knowledge_point=knowledge_point,
            options_json=options_json,
            correct_answer=payload.correct_answer,
            analysis=payload.analysis,
            source_type=payload.source_type,
            source_user_id=current_user["id"],
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
                   ai_label, final_label, knowledge_point, confidence, mastery_status,
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
                "knowledge_point": row["knowledge_point"],
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
                   ai_label, final_label, knowledge_point, confidence, mastery_status,
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
            "knowledge_point": row["knowledge_point"],
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

    conn = _connect_db()
    try:
        current = conn.execute(
            "SELECT id FROM questions WHERE id=? AND user_id=? AND is_deleted=0",
            (question_id, current_user["id"]),
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="题目不存在")

        existing = conn.execute(
            "SELECT stem, final_label FROM questions WHERE id=? AND user_id=?",
            (question_id, current_user["id"]),
        ).fetchone()
        stem_for_kp = updates.get("stem") or (existing["stem"] if existing else "")
        label_for_kp = updates.get("final_label") or (existing["final_label"] if existing else "")
        if stem_for_kp and label_for_kp:
            updates["knowledge_point"] = _infer_knowledge_point(stem_for_kp, label_for_kp)

        now = _utc_now()
        updates["updated_at"] = now
        set_sql = ", ".join([f"{k}=?" for k in updates])

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


@api_router.get("/dashboard/mastery-overview", response_model=ApiResponse)
def dashboard_mastery_overview(current_user: dict[str, str] = Depends(get_current_user)):
    conn = _connect_db()
    try:
        rows = conn.execute(
            """
            SELECT mastery_status, COUNT(1) AS cnt
            FROM questions
            WHERE is_deleted=0 AND user_id=?
            GROUP BY mastery_status
            """,
            (current_user["id"],),
        ).fetchall()
    finally:
        conn.close()

    status_count = {status: 0 for status in MASTERY_SET}
    for row in rows:
        status_count[row["mastery_status"]] = row["cnt"]

    total = sum(status_count.values())
    mastered = status_count.get("mastered", 0)
    reviewed = status_count.get("reviewed", 0)
    mastery_rate = (mastered / total) if total else 0.0
    review_rate = ((mastered + reviewed) / total) if total else 0.0
    return ok(
        {
            "total": total,
            "status_count": status_count,
            "mastery_rate": round(mastery_rate, 4),
            "review_rate": round(review_rate, 4),
        }
    )


@api_router.get("/dashboard/study-trend", response_model=ApiResponse)
def dashboard_study_trend(
    days: int = Query(default=7, ge=3, le=60),
    current_user: dict[str, str] = Depends(get_current_user),
):
    conn = _connect_db()
    try:
        created_rows = conn.execute(
            """
            SELECT strftime('%Y-%m-%d', created_at) AS d, COUNT(1) AS cnt
            FROM questions
            WHERE is_deleted=0 AND user_id=?
              AND datetime(created_at) >= datetime('now', ?)
            GROUP BY d
            ORDER BY d ASC
            """,
            (current_user["id"], f"-{days - 1} days"),
        ).fetchall()

        review_rows = conn.execute(
            """
            SELECT strftime('%Y-%m-%d', created_at) AS d, COUNT(1) AS cnt
            FROM question_review_logs
            WHERE user_id=?
              AND datetime(created_at) >= datetime('now', ?)
            GROUP BY d
            ORDER BY d ASC
            """,
            (current_user["id"], f"-{days - 1} days"),
        ).fetchall()
    finally:
        conn.close()

    created_map = {row["d"]: row["cnt"] for row in created_rows}
    review_map = {row["d"]: row["cnt"] for row in review_rows}

    labels: list[str] = []
    created_counts: list[int] = []
    reviewed_counts: list[int] = []
    today = datetime.utcnow().date()
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        key = day.strftime("%Y-%m-%d")
        labels.append(key)
        created_counts.append(int(created_map.get(key, 0)))
        reviewed_counts.append(int(review_map.get(key, 0)))

    return ok(
        {
            "labels": labels,
            "created_counts": created_counts,
            "reviewed_counts": reviewed_counts,
            "days": days,
        }
    )


@api_router.get("/dashboard/weak-topics", response_model=ApiResponse)
def dashboard_weak_topics(current_user: dict[str, str] = Depends(get_current_user)):
    conn = _connect_db()
    try:
        rows = conn.execute(
            """
            SELECT
                final_label,
                COUNT(1) AS total_cnt,
                SUM(CASE WHEN mastery_status='mastered' THEN 1 ELSE 0 END) AS mastered_cnt,
                SUM(CASE WHEN mastery_status='unreviewed' OR mastery_status='careless' THEN 1 ELSE 0 END) AS weak_cnt
            FROM questions
            WHERE is_deleted=0 AND user_id=?
            GROUP BY final_label
            ORDER BY weak_cnt DESC, total_cnt DESC
            """,
            (current_user["id"],),
        ).fetchall()
    finally:
        conn.close()

    items = []
    for row in rows:
        total_cnt = int(row["total_cnt"] or 0)
        weak_cnt = int(row["weak_cnt"] or 0)
        mastered_cnt = int(row["mastered_cnt"] or 0)
        weak_rate = (weak_cnt / total_cnt) if total_cnt else 0.0
        items.append(
            {
                "label": row["final_label"],
                "total_cnt": total_cnt,
                "weak_cnt": weak_cnt,
                "mastered_cnt": mastered_cnt,
                "weak_rate": round(weak_rate, 4),
            }
        )

    return ok({"items": items})


@api_router.get("/dashboard/weak-knowledge-points", response_model=ApiResponse)
def dashboard_weak_knowledge_points(current_user: dict[str, str] = Depends(get_current_user)):
    conn = _connect_db()
    try:
        items = _get_weak_knowledge_points(conn, current_user["id"], limit=10)
    finally:
        conn.close()
    return ok({"items": items})


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
    source_type = payload.source_type.strip().lower() if payload.source_type else "manual"
    if source_type not in SOURCE_TYPE_SET:
        raise HTTPException(status_code=400, detail=f"source_type 非法: {source_type}")
    result = _predict_text(payload.text, source_type=source_type)
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

    result = _predict_text(text, source_type="manual")
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
    source_type = payload.source_type.strip().lower() if payload.source_type else "manual"
    if source_type not in SOURCE_TYPE_SET:
        raise HTTPException(status_code=400, detail=f"source_type 非法: {source_type}")
    result = _predict_text(payload.text, source_type=source_type)
    return ok(PredictResponse(**result).model_dump())


app.include_router(api_router)