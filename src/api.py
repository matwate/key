import os
import tempfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any, Optional

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth_routes import router as auth_router
from .database import init_db
from .receipt_processor import ReceiptProcessor


class ReceiptResponse(BaseModel):
    success: bool
    total_items: int = 0
    products: list[dict[str, Any]] = []
    message: Optional[str] = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    yield


app = FastAPI(title="Receipt Analysis API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

_processor = None


def get_processor():
    global _processor
    if _processor is None:
        _processor = ReceiptProcessor()
    return _processor


@app.get("/")
async def root():
    return {
        "message": "Receipt Analysis API",
        "version": "1.0.0",
        "endpoints": {"POST /api/receipt/analyze": "Upload and analyze receipt image"},
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/receipt/analyze", response_model=ReceiptResponse)
async def analyze_receipt(file: UploadFile = File(...)):
    try:
        proc = get_processor()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=f".{file.filename.rsplit('.', 1)[-1] if file.filename else 'tmp'}",
        ) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        result = proc.process_receipt(tmp_path)

        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        if result.is_err():
            return {
                "success": False,
                "total_items": 0,
                "products": [],
                "message": result.unwrap_err(),
            }

        analysis = result.unwrap()
        return {
            "success": True,
            "total_items": analysis.total_items,
            "products": [asdict(p) for p in analysis.products],
        }
    except Exception as e:
        return {
            "success": False,
            "total_items": 0,
            "products": [],
            "message": f"Internal server error: {str(e)}",
        }
