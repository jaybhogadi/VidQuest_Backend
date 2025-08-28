from pydantic import BaseModel, Field
from typing import List

# --------- Data Models ---------
class Option(BaseModel):
    id: str = Field(..., pattern=r"^[A-D]$")
    text: str

class MCQQuestion(BaseModel):
    question: str
    options: List[Option]
    correct_answer: str = Field(..., pattern=r"^[A-D]$")
    explanation: str = ""

class VideoUploadRequest(BaseModel):
    path_name: str
    requestId: str
    num_questions: str