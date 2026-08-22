from pydantic import BaseModel


class SearchResultOut(BaseModel):
    file_id: str
    path: str
    start_line: int
    end_line: int
    symbol_name: str | None
    symbol_kind: str | None
    score: float


class SearchResponseOut(BaseModel):
    query: str
    results: list[SearchResultOut]