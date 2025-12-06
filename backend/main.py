"""FastAPI application entry point."""
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.config import settings
from backend.api.routes import resources, logs, llm, fixes, mcp, gcp_failures
from backend.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="MCP-Enabled Infrastructure Orchestration System"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests and responses."""
    start_time = time.time()
    
    # Log request
    logger.info(f"→ {request.method} {request.url.path} | Client: {request.client.host if request.client else 'unknown'}")
    logger.debug(f"  Query params: {dict(request.query_params)}")
    
    # Process request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log response
        logger.info(f"← {request.method} {request.url.path} | Status: {response.status_code} | Time: {process_time:.3f}s")
        
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"✗ {request.method} {request.url.path} | Error: {str(e)} | Time: {process_time:.3f}s", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )

# Include routers
app.include_router(resources.router, prefix=settings.API_PREFIX)
app.include_router(logs.router, prefix=settings.API_PREFIX)
app.include_router(llm.router, prefix=settings.API_PREFIX)
app.include_router(fixes.router, prefix=settings.API_PREFIX)
app.include_router(mcp.router, prefix=settings.API_PREFIX)
app.include_router(gcp_failures.router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "MCP Infrastructure Orchestrator API",
        "version": settings.API_VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

