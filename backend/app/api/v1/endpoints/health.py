from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Check API availability")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "trust-infrastructure-api"}
