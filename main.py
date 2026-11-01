from fastapi.responses import FileResponse
from pathlib import Path
from ai_agent import calculate_lead_score, calculate_priority
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from database import engine, Base, get_db
from models import Lead
from automation import send_lead_to_n8n


app = FastAPI(title="LeadFlow AI")

# Create database tables
Base.metadata.create_all(bind=engine)


# Input validation
class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=20)
    service: str = Field(min_length=2, max_length=150)


# Home API - Serve Website
@app.get("/")
def home():
    return FileResponse("static/index.html")


# GET: Fetch all leads
@app.get("/leads")
def get_leads(db: Session = Depends(get_db)):
    return db.query(Lead).all()


# POST: Create a new lead
@app.post("/leads")
def create_lead(
    lead: LeadCreate,
    db: Session = Depends(get_db)
):
    # Calculate lead score
    score = calculate_lead_score(
        lead.name,
        lead.email,
        lead.service
    )

    # Calculate priority
    priority = calculate_priority(score)

    # Create new lead
    new_lead = Lead(
        name=lead.name,
        email=lead.email,
        phone=lead.phone,
        service=lead.service,
        status="New",
        lead_score=score,
        priority=priority
    )

    # Save lead to PostgreSQL
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)

    # Send lead to n8n
    try:
        send_lead_to_n8n(new_lead)
    except Exception as error:
        print("n8n automation error:", error)

    return {
        "message": "Lead created successfully!",
        "lead": new_lead
    }


# PUT: Update an existing lead
@app.put("/leads/{lead_id}")
def update_lead(
    lead_id: int,
    updated_lead: LeadCreate,
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id
    ).first()

    if lead is None:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    lead.name = updated_lead.name
    lead.email = updated_lead.email
    lead.service = updated_lead.service

    # Recalculate score and priority after update
    score = calculate_lead_score(
        lead.name,
        lead.email,
        lead.service
    )

    lead.lead_score = score
    lead.priority = calculate_priority(score)

    db.commit()
    db.refresh(lead)

    return {
        "message": "Lead updated successfully!",
        "lead": lead
    }


# DELETE: Delete an existing lead
@app.delete("/leads/{lead_id}")
def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id
    ).first()

    if lead is None:
        raise HTTPException(
            status_code=404,
            detail="Lead not found"
        )

    db.delete(lead)
    db.commit()

    return {
        "message": "Lead deleted successfully!"
    }


# GET: Filter leads by priority
@app.get("/leads/priority/{priority}")
def get_leads_by_priority(
    priority: str,
    db: Session = Depends(get_db)
):
    leads = db.query(Lead).filter(
        Lead.priority == priority.capitalize()
    ).all()

    return leads


# GET: Search leads by name
@app.get("/leads/search/{name}")
def search_leads(
    name: str,
    db: Session = Depends(get_db)
):
    leads = db.query(Lead).filter(
        Lead.name.ilike(f"%{name}%")
    ).all()

    return leads