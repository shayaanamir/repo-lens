from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)


class SourceOut(BaseModel):
    path: str
    start_line: int
    end_line: int


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut]


class ExplainResponse(BaseModel):
    explanation: str
    sources: list[SourceOut]


class InterviewPrepRequest(BaseModel):
    context: str | None = None


class QAOut(BaseModel):
    question: str
    answer: str


class InterviewPrepResponse(BaseModel):
    pitch: str
    talking_points: list[str]
    questions: list[QAOut]
    grounded_in: list[SourceOut]