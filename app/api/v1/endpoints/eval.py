# FastAPI endpoint for document evaluation
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import shutil
import os
from app.services.project_doc import GeminiDocEvaluator
from app.prompts import system_prompt
from app.api.v1.schemas.eval import EvaluationResponse

router = APIRouter()

@router.post("/upload", response_model=EvaluationResponse)
async def evaluate_document(file: UploadFile = File(...)):
    # Save uploaded file to a temp location
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[-1]) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {e}")
    prompt = system_prompt.PROMPT
    evaluator = GeminiDocEvaluator()
    try:
        evaluation = await evaluator.evaluate(tmp_path, prompt)
    except Exception as e:
        os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}")
    os.remove(tmp_path)
    return EvaluationResponse(evaluation=evaluation)
