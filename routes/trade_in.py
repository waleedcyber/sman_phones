from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_db
from models import TradeIn
from schemas import TradeInCreate, TradeInOut
from auth import get_current_admin
from typing import List

router = APIRouter()

@router.post("/trade-in", response_model=TradeInOut)
def submit_trade_in(data: TradeInCreate, db: Session = Depends(get_db)):
    trade = TradeIn(**data.model_dump())
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade

@router.get("/admin/trade-ins", response_model=List[TradeInOut])
def get_trade_ins(
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    return db.query(TradeIn).order_by(TradeIn.timestamp.desc()).all()

@router.put("/admin/trade-ins/{trade_id}/status")
def update_trade_in_status(
    trade_id: int,
    status: str,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    trade = db.query(TradeIn).filter(TradeIn.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade-in not found")
    trade.status = status
    db.commit()
    return {"message": "Status updated"}