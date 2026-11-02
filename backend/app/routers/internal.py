import hmac

from fastapi import APIRouter

from app import jobs
from app.config import get_settings
from app.routers.groups import Sender
from app.security import DB, NOT_FOUND, Token

router = APIRouter()


@router.post("/internal/jobs/run")
def run_jobs(token: Token, db: DB, sender: Sender) -> dict[str, object]:
    """For the host's cron. Bearer CRON_SECRET; 404 when unset or wrong."""
    secret = get_settings().cron_secret
    if not secret or not hmac.compare_digest(token.encode(), secret.encode()):
        raise NOT_FOUND
    report = jobs.run(db, sender)
    return {"deleted_groups": report.deleted_groups, "sent": report.sent}
