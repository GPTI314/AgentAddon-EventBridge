from fastapi import FastAPI
from .config import get_settings
from .logging import setup_logging
from .api.router import router
from .api.rules_router import router as rules_router
from .api.ws_router import router as ws_router
from .api.metrics_router import router as metrics_router
from .middleware.correlation import CorrelationMiddleware
from .middleware.validation import ValidationMiddleware
from .middleware.error_handler import ErrorHandlerMiddleware

settings = get_settings()
setup_logging(settings.LOG_JSON)

app = FastAPI(title="AgentAddon EventBridge", version="0.1.0")

# Add middleware (order matters - last added is first executed)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(ValidationMiddleware)
app.add_middleware(CorrelationMiddleware)

app.include_router(router)
app.include_router(rules_router)
app.include_router(ws_router)
app.include_router(metrics_router)

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
