# Entrypoint for running the FastAPI application with uv.

import uvicorn


def main() -> None:
    """Start the FastAPI server using uvicorn."""
    uvicorn.run(
        "meetingai_backend.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
