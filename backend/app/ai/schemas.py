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