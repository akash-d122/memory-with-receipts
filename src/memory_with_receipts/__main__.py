import uvicorn


def main() -> None:
    """Run the development API server."""
    uvicorn.run(
        "memory_with_receipts.api.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
