from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.execution import VisualizeRequest, VisualizeResponse
from app.services.llm import TraceServiceError
from app.services.trace_generator import generate_trace

router = APIRouter()


# A plain `def`, not `async def`: generate_trace blocks for seconds on the model call,
# and FastAPI runs sync routes in a threadpool so other requests are not held up.
@router.post("/api/visualize", response_model=VisualizeResponse)
def visualize(body: VisualizeRequest) -> VisualizeResponse:
    """`ok` and `unsupported` are both normal 200 answers. Only a service failure is an error."""
    try:
        return generate_trace(body.code)
    except TraceServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
