"""Keep published descriptions stable across supported Python versions."""

import pytest
from fastapi import FastAPI

from app.core.feature_http import install_feature_http


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Unprocessable Entity", "Unprocessable Content"),
        ("Unprocessable Content", "Unprocessable Content"),
        ("Validation Error", "Validation Error"),
        ("Unsupported evidence", "Unsupported evidence"),
    ],
)
def test_422_descriptions_preserve_contract(description: str, expected: str) -> None:
    app = FastAPI()
    install_feature_http(app)

    @app.get("/example", responses={422: {"description": description}})
    async def example() -> dict[str, bool]:
        return {"ok": True}

    response = app.openapi()["paths"]["/example"]["get"]["responses"]["422"]
    assert response["description"] == expected
