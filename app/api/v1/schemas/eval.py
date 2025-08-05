from pydantic import BaseModel

class EvaluationResponse(BaseModel):
    evaluation: str

class EvaluationRequest(BaseModel):
    # Placeholder for any extra fields if needed in future
    pass
