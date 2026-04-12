# -*- coding: utf-8 -*-
"""
后端 API 入口

运行方式：
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from inference import TextClassifier


class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待分类文本")


class PredictResponse(BaseModel):
    label: str
    confidence: float


class ApiResponse(BaseModel):
    code: int
    message: str
    data: Any = None


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

app.mount("/web", StaticFiles(directory=str(web_dir)), name="web")


def ok(data=None, message="ok"):
    return ApiResponse(code=0, message=message, data=data)


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


@app.get("/")
def index_page():
    return FileResponse(web_dir / "index.html")


@app.get("/health")
def health_check():
    return ok({"status": "ok"})


@api_router.get("/health")
def health_check_v1():
    return ok({"status": "ok", "version": "v1"})


@api_router.get("/labels")
def list_labels():
    return ok({"labels": sorted(classifier.label2idx.keys())})


@api_router.post("/predict", response_model=ApiResponse)
def predict_v1(payload: PredictRequest):
    result = _predict_text(payload.text)
    return ok(PredictResponse(**result).model_dump())


@app.get("/predict")
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


@app.post("/predict", response_model=ApiResponse)
def predict(payload: PredictRequest):
    result = _predict_text(payload.text)
    return ok(PredictResponse(**result).model_dump())


app.include_router(api_router)