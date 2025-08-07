from pydantic import BaseModel, Field
from typing import Optional

class EvaluationResponse(BaseModel):
    evaluation: str = Field(..., description="Detailed evaluation in markdown format with rubric-based scoring")
    step_name: str = Field(..., description="The name of the step being evaluated")
    deliverable_name: str = Field(..., description="The name of the deliverable being evaluated")
    score: Optional[float] = Field(None, description="Numerical score based on the rubric (0-10)")

class EvaluationRequest(BaseModel):
    step_name: str = Field(..., description="The step name from the rubric (e.g., 'Research & Data Collection')")
    deliverable_name: str = Field(..., description="The specific deliverable name (e.g., 'Survey Results', 'Data Analysis Report')")
    additional_context: Optional[str] = Field(
        None, 
        description="Any additional context about the submission that might help with evaluation"
    )
