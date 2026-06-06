import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from database import init_db
from routes.users import router as users_router
from routes.channels import router as channels_router


def _run_digest():
    from scheduler import run_weekly_digest
    run_weekly_digest()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(_run_digest, CronTrigger(day_of_week="sat", hour=12, minute=0))
    scheduler.start()
    print("[scheduler] Weekly digest scheduled for Saturdays at 12:00 UTC")

    yield

    scheduler.shutdown()


app = FastAPI(title="Investing Podcast Digest", lifespan=lifespan)

app.include_router(users_router)
app.include_router(channels_router)


# Test/admin endpoint to manually trigger the digest
@app.post("/api/admin/trigger-digest")
async def trigger_digest(request: Request):
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.getenv("ADMIN_SECRET", ""):
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})
    import threading
    threading.Thread(target=_run_digest, daemon=True).start()
    return {"message": "Digest triggered in background"}


# Unsubscribe page (GET redirect from email link)
@app.get("/unsubscribe")
async def unsubscribe_page(token: str):
    from database import SessionLocal
    from models import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.access_token == token).first()
        if user:
            user.active = False
            db.commit()
    finally:
        db.close()
    return FileResponse("static/unsubscribed.html")


# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/dashboard")
async def dashboard():
    return FileResponse("static/dashboard.html")


@app.get("/")
async def index():
    return FileResponse("static/index.html")
