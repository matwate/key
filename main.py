if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=5003,
        reload=True,
    )
