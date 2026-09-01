from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    product_name: str = Field(...)


class GenerateResponse(BaseModel):
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=300)
    bullets: list[str]
    keywords_used: list[str]
    sources: dict
