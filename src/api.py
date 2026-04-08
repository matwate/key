import os
import tempfile
from dataclasses import asdict

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .receipt_processor import ReceiptProcessor

app = FastAPI(title="Receipt Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.post("/api/receipt/analyze")
async def analyze_receipt(file: UploadFile = File(...)):
    try:
        proc = get_processor()

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{file.filename.split('.')[-1]}"
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
