import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Lead
from ..schemas import LeadIn, LeadOut

router = APIRouter(prefix="/leads", tags=["leads"])
logger = logging.getLogger(__name__)

# Very small in-process throttle so the public endpoint can't be spammed from one worker.
_recent: dict[str, tuple[int, int]] = {}  # phone -> (hour_bucket, count)
_MAX_PER_HOUR = 5


@router.post("", response_model=LeadOut, status_code=201)
def create_lead(body: LeadIn, db: Session = Depends(get_db)):
    key = body.phone.strip()
    bucket = int(time.time() // 3600)
    seen_bucket, count = _recent.get(key, (bucket, 0))
    count = count + 1 if seen_bucket == bucket else 1
    if count > _MAX_PER_HOUR:
        raise HTTPException(429, "Too many requests from this number. Please try again later.")
    _recent[key] = (bucket, count)
    lead = Lead(
        name=body.name.strip(),
        phone=key,
        email=body.email,
        interest=(body.interest or "").strip() or None,
        preferred_time=(body.preferred_time or "").strip() or None,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    logger.info("Lead captured: id=%s interest=%s", lead.id, lead.interest)
    return lead
