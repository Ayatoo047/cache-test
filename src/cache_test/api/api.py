from fastapi import APIRouter, Request, Response

from cache_test.schemas.health import Health
from cache_test.utils.envelope import ApiResponse, _success

router = APIRouter()


@router.get("/health", include_in_schema=False)
def health(request: Request, response: Response) -> ApiResponse[Health]:
    return _success(request, response, Health(status="ok"), "Service is healthy")
