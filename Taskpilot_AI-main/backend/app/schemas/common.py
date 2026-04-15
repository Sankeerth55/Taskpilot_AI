from datetime import datetime
from pydantic import BaseModel


class APIError(BaseModel):
    error: str
    message: str


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
