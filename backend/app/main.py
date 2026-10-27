from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .crypto.suites import IntegrityError
from .db import init_db
from .routers import attachments, auth, me, officer, reports, verifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Safe Report API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Cipher", "X-Integrity", "X-Decrypt-Ms", "Content-Disposition"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=500, content={"detail": f"Integrity verification failed: {exc}"})


for r in (auth.router, me.router, reports.router, attachments.router, officer.router, verifications.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok"}
