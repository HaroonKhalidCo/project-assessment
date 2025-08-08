# FastAPI endpoint for document and media evaluation
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from fastapi.responses import JSONResponse
import tempfile
import shutil
import os
from typing import List, Optional
from app.services.project_doc import GeminiDocEvaluator
from app.prompts import system_prompt
from app.api.v1.schemas.eval import EvaluationResponse, EvaluationRequest

router = APIRouter(tags=["evaluation"])

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {
    # Document formats
    '.pdf', '.docx', '.doc', '.txt', '.rtf', '.odt', '.md',
    # Image formats
    '.jpg', '.jpeg', '.png', '.webp', '.gif',
    # Video formats
    '.mp4', '.webm', '.mov', '.avi', '.mkv',
    # Audio formats
    '.mp3', '.wav', '.ogg', '.m4a'
}

def is_allowed_file(filename: str) -> bool:
    """Check if the file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {ext.lstrip('.') for ext in ALLOWED_EXTENSIONS}

@router.post("/evaluate", response_model=EvaluationResponse, status_code=status.HTTP_200_OK)
async def evaluate_document(
    file: UploadFile = File(..., description="The file to evaluate"),
    step_name: str = "",
    deliverable_name: str = "",
    additional_context: Optional[str] = None
):
    """
    Evaluate a document, image, audio, or video file for a specific step and deliverable.
    
    This endpoint accepts various file types including documents (PDF, DOCX, etc.),
    images (JPG, PNG, etc.), audio (MP3, WAV), and video (MP4, WebM, etc.) files.
    
    The evaluation will be performed based on the specified step and deliverable criteria.
    """
    # Validate file type
    if not file.filename or not is_allowed_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_file_type",
                "message": f"File type not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                "allowed_types": sorted(ALLOWED_EXTENSIONS)
            }
        )
    
    # Validate required fields
    if not step_name or not deliverable_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "missing_required_fields",
                "message": "Both 'step_name' and 'deliverable_name' are required fields",
                "required_fields": ["step_name", "deliverable_name"]
            }
        )
    
    # Save uploaded file to a temp location
    tmp_path = None
    try:
        # Ensure the file has content
        if not file.size or file.size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "empty_file",
                    "message": "The uploaded file is empty"
                }
            )
            
        # Limit file size (e.g., 50MB)
        max_file_size = 50 * 1024 * 1024  # 50MB
        if file.size > max_file_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "file_too_large",
                    "message": f"File size exceeds the maximum allowed size of 50MB",
                    "max_size_mb": 50,
                    "actual_size_mb": round(file.size / (1024 * 1024), 2)
                }
            )
            
        file_extension = os.path.splitext(file.filename)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
            # Read file in chunks to handle large files
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                tmp.write(chunk)
            tmp_path = tmp.name
            
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "file_processing_error",
                "message": f"Failed to process uploaded file: {str(e)}"
            }
        )
    
    # Process the file with step and deliverable context
    evaluator = GeminiDocEvaluator()
    
    try:
        # Get the evaluation from Gemini
        evaluation = await evaluator.evaluate(
            file_path=tmp_path,
            step_name=step_name,
            deliverable_name=deliverable_name,
            additional_context=additional_context
        )
        
        # Parse the evaluation to extract score if possible
        score = None
        if evaluation:
            # Try to extract score from the evaluation text
            import re
            score_match = re.search(r'Overall Score:\s*(\d+)/', evaluation)
            if score_match:
                try:
                    score = float(score_match.group(1))
                except (ValueError, IndexError):
                    pass
        
        # Return the evaluation with the step and deliverable information
        return EvaluationResponse(
            evaluation=evaluation,
            step_name=step_name,
            deliverable_name=deliverable_name,
            score=score
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        error_detail = str(e)
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        # Handle specific Gemini API errors
        if "FAILED_PRECONDITION" in error_detail or "not in an ACTIVE state" in error_detail:
            status_code = status.HTTP_400_BAD_REQUEST
            error_detail = "The uploaded file could not be processed. Please try again with a different file."
        
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": "evaluation_failed",
                "message": f"Evaluation failed: {error_detail}",
                "step": step_name,
                "deliverable": deliverable_name
            }
        )
        
    finally:
        # Clean up the temporary file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception as e:
                print(f"Warning: Failed to delete temporary file {tmp_path}: {str(e)}")
