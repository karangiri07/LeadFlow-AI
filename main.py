import os
import json
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from database import engine, Base, get_db, SessionLocal
from models import Lead, WhatsAppContact, WhatsAppMessage, KnowledgeDocument, WhatsAppSetting
from ai_agent import calculate_lead_score, calculate_priority
from automation import send_lead_to_n8n
from rag_engine import seed_default_knowledge, RAGEngine

# Initialize tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="LeadFlow AI - WhatsApp Automation & RAG Admin Panel")

# Enable CORS for admin dashboard interactions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seed knowledge base on startup
@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        seed_default_knowledge(db)
        _seed_sample_whatsapp_if_empty(db)
    except Exception as e:
        print("Startup seeding notice:", e)
    finally:
        db.close()


def _seed_sample_whatsapp_if_empty(db: Session):
    """Seed a couple of realistic conversations if none exist, showing RAG capabilities."""
    if db.query(WhatsAppContact).count() == 0:
        # Sample 1: Pricing enquiry
        c1 = WhatsAppContact(
            phone_number="+919876543210",
            name="Rahul Sharma",
            status="active",
            ai_mode="auto",
            last_message="Here is the information regarding Pricing Plans & Packages...",
            unread_count=0,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        )
        db.add(c1)
        db.flush()

        m1 = WhatsAppMessage(
            contact_id=c1.id,
            sender="user",
            sender_name="Rahul Sharma",
            text="Hi! Do you have website packages and what are your pricing plans?",
            status="received",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        )
        db.add(m1)

        docs = RAGEngine.retrieve_relevant_documents(m1.text, db)
        resp, sources = RAGEngine.generate_grounded_response(m1.text, docs, c1.name)

        m2 = WhatsAppMessage(
            contact_id=c1.id,
            sender="bot",
            sender_name="LeadFlow RAG Bot",
            text=resp,
            status="sent",
            rag_sources=json.dumps(sources),
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2, seconds=-15)
        )
        db.add(m2)

        # Sample 2: Lead capture enquiry
        c2 = WhatsAppContact(
            phone_number="+15550192834",
            name="Priya Patel",
            status="active",
            ai_mode="auto",
            last_message="I've registered your consultation request with our team!",
            unread_count=1,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=5)
        )
        db.add(c2)
        db.flush()

        lead2 = Lead(
            name="Priya Patel",
            email="priya@techflow.io",
            phone="+15550192834",
            service="AI Automation",
            status="New (WhatsApp)",
            lead_score=70,
            priority="Hot"
        )
        db.add(lead2)
        db.flush()
        c2.lead_id = lead2.id

        m3 = WhatsAppMessage(
            contact_id=c2.id,
            sender="user",
            sender_name="Priya Patel",
            text="I need an end-to-end AI automation workflow with n8n. My email is priya@techflow.io, can we schedule a demo call?",
            status="received",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=5)
        )
        db.add(m3)

        docs2 = RAGEngine.retrieve_relevant_documents(m3.text, db)
        resp2, sources2 = RAGEngine.generate_grounded_response(m3.text, docs2, c2.name)

        m4 = WhatsAppMessage(
            contact_id=c2.id,
            sender="bot",
            sender_name="LeadFlow RAG Bot",
            text=resp2,
            status="sent",
            rag_sources=json.dumps(sources2),
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=5, seconds=-10)
        )
        db.add(m4)

        db.commit()


def send_whatsapp_cloud_api_message(to_phone: str, text: str) -> Optional[dict]:
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    if not token or not phone_id:
        print("[WhatsApp] Credentials missing.")
        return {
            "success": False,
            "message_id": None,
            "error": "WhatsApp credentials missing"
        }

    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text
        }
    }

    try:
        res = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=10
        )

        response_data = res.json()
        res.raise_for_status()

        messages = response_data.get("messages", [])
        whatsapp_message_id = messages[0].get("id") if messages else None

        print(f"[WhatsApp] Accepted by Meta. Message ID: {whatsapp_message_id}")

        return {
            "success": True,
            "message_id": whatsapp_message_id,
            "response": response_data
        }

    except requests.exceptions.RequestException as e:
        error_details = e.response.text if e.response is not None else str(e)

        print(f"[WhatsApp] API request failed: {e}")
        print(f"[WhatsApp] Error details: {error_details}")

        return {
            "success": False,
            "message_id": None,
            "error": error_details
        }



# -------------------------------------------------------------
# Input Validation Models
# -------------------------------------------------------------
class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=20)
    service: str = Field(min_length=2, max_length=150)


class ReplyRequest(BaseModel):
    text: str = Field(min_length=1)


class SimulateMessageRequest(BaseModel):
    phone: str = Field(min_length=5, max_length=25)
    name: Optional[str] = "WhatsApp User"
    text: str = Field(min_length=1)


class KnowledgeDocCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    category: str = "general"
    content: str = Field(min_length=5)
    tags: Optional[str] = ""


class KnowledgeDocUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    category: str = "general"
    content: str = Field(min_length=5)
    tags: Optional[str] = ""
    is_active: Optional[bool] = True


class RAGTestRequest(BaseModel):
    query: str = Field(min_length=1)


# -------------------------------------------------------------
# Static HTML Web Routes
# -------------------------------------------------------------
@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/dashboard")
def dashboard():
    return FileResponse("static/dashboard.html")


@app.get("/admin")
def admin_redirect():
    return FileResponse("static/dashboard.html")


@app.get("/privacy")
def privacy_policy():
    return FileResponse("static/privacy.html")


@app.get("/data-deletion")
def data_deletion():
    return FileResponse("static/data-deletion.html")


@app.get("/terms")
def terms_of_service():
    return FileResponse("static/terms.html")


# -------------------------------------------------------------
# Lead Management APIs (Existing + Enhanced)
# -------------------------------------------------------------
@app.get("/leads")
def get_leads(db: Session = Depends(get_db)):
    return db.query(Lead).order_by(Lead.id.desc()).all()


@app.post("/leads")
def create_lead(lead: LeadCreate, db: Session = Depends(get_db)):
    score = calculate_lead_score(lead.name, lead.email, lead.service)
    priority = calculate_priority(score)

    new_lead = Lead(
        name=lead.name,
        email=lead.email,
        phone=lead.phone,
        service=lead.service,
        status="New",
        lead_score=score,
        priority=priority
    )

    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)

    try:
        send_lead_to_n8n(new_lead)
    except Exception as error:
        print("n8n automation error:", error)

    return {"message": "Lead created successfully!", "lead": new_lead}


@app.put("/leads/{lead_id}")
def update_lead(lead_id: int, updated_lead: LeadCreate, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.name = updated_lead.name
    lead.email = updated_lead.email
    lead.service = updated_lead.service

    score = calculate_lead_score(lead.name, lead.email, lead.service)
    lead.lead_score = score
    lead.priority = calculate_priority(score)

    db.commit()
    db.refresh(lead)
    return {"message": "Lead updated successfully!", "lead": lead}


@app.delete("/leads/{lead_id}")
def delete_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()
    return {"message": "Lead deleted successfully!"}


@app.get("/leads/priority/{priority}")
def get_leads_by_priority(priority: str, db: Session = Depends(get_db)):
    return db.query(Lead).filter(Lead.priority == priority.capitalize()).all()


@app.get("/leads/search/{name}")
def search_leads(name: str, db: Session = Depends(get_db)):
    return db.query(Lead).filter(Lead.name.ilike(f"%{name}%")).all()


# -------------------------------------------------------------
# WhatsApp Webhook Verification & Processing (Meta Cloud API)
# -------------------------------------------------------------
@app.get("/webhook")
def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "leadflow_verify_token")
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@app.post("/webhook")
async def receive_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    data = await request.json()

    print("WhatsApp Webhook Received:", json.dumps(data, indent=2))

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # 1. Process outgoing message status updates
                for status_item in value.get("statuses", []):
                    whatsapp_message_id = status_item.get("id")
                    meta_status = status_item.get("status")

                    if not whatsapp_message_id or not meta_status:
                        continue

                    message = db.query(WhatsAppMessage).filter(
                        WhatsAppMessage.whatsapp_message_id
                        == whatsapp_message_id
                    ).first()

                    if message:
                        if meta_status in ["sent", "delivered", "read", "failed"]:
                            message.status = meta_status

                        if meta_status == "failed":
                            errors = status_item.get("errors", [])
                            message.error_details = json.dumps(errors)

                        print(
                            f"[WhatsApp Status] "
                            f"{whatsapp_message_id}: {meta_status}"
                        )

                # 2. Process incoming customer messages
                messages = value.get("messages", [])
                contacts = value.get("contacts", [])

                for incoming_message in messages:
                    phone = incoming_message.get("from")

                    if incoming_message.get("type") != "text":
                        continue

                    message_text = incoming_message.get(
                        "text", {}
                    ).get("body", "").strip()

                    if not phone or not message_text:
                        continue

                    customer_name = "WhatsApp User"

                    for item in contacts:
                        if item.get("wa_id") == phone:
                            customer_name = item.get(
                                "profile", {}
                            ).get("name", customer_name)
                            break

                    _process_incoming_whatsapp_message(
                        phone=phone,
                        customer_name=customer_name,
                        message_text=message_text,
                        db=db
                    )

        db.commit()

    except Exception as error:
        db.rollback()
        print("WhatsApp webhook database error:", error)

        raise HTTPException(
            status_code=500,
            detail="Message processing failed"
        )

    return {"status": "received"}

def _process_incoming_whatsapp_message(
    phone: str,
    customer_name: str,
    message_text: str,
    db: Session
) -> dict:
    """
    Process an incoming WhatsApp message:
    1. Find or create contact.
    2. Save incoming message.
    3. Extract lead information.
    4. Generate AI reply if AI mode is enabled.
    5. Send reply through WhatsApp Cloud API.
    """

    contact = (
        db.query(WhatsAppContact)
        .filter(WhatsAppContact.phone_number == phone)
        .first()
    )

    if contact is None:
        contact = WhatsAppContact(
            phone_number=phone,
            name=customer_name or "WhatsApp User",
            status="active",
            ai_mode="auto",
            unread_count=0
        )
        db.add(contact)
        db.flush()

    elif customer_name and customer_name != "WhatsApp User":
        contact.name = customer_name

    # Save incoming customer message
    user_msg = WhatsAppMessage(
        contact_id=contact.id,
        sender="user",
        sender_name=contact.name,
        text=message_text,
        status="received"
    )

    db.add(user_msg)

    contact.last_message = message_text
    contact.last_message_at = datetime.datetime.utcnow()
    contact.unread_count = (contact.unread_count or 0) + 1

    db.commit()
    db.refresh(user_msg)

    # Extract lead information
    lead_info = RAGEngine.check_and_extract_lead(
        user_message=message_text,
        phone_number=phone,
        contact_name=contact.name,
        db=db,
        contact=contact
    )

    bot_msg = None
    sources = []

    # Generate and send reply only when AI mode is enabled
    if contact.ai_mode == "auto":

        docs = RAGEngine.retrieve_relevant_documents(
            message_text,
            db
        )

        reply_text, sources = RAGEngine.generate_grounded_response(
            message_text,
            docs,
            contact.name
        )

        # Save bot reply before sending
        bot_msg = WhatsAppMessage(
            contact_id=contact.id,
            sender="bot",
            sender_name="LeadFlow RAG Bot",
            text=reply_text,
            rag_sources=json.dumps(sources),
            status="pending"
        )

        db.add(bot_msg)
        contact.last_message = reply_text
        contact.last_message_at = datetime.datetime.utcnow()

        db.commit()
        db.refresh(bot_msg)

        # Send exactly once through Meta Cloud API
        result = send_whatsapp_cloud_api_message(
            phone,
            reply_text
        )

        if result is not None and result.get("success"):
            bot_msg.status = "sent"
            bot_msg.whatsapp_message_id = result.get("message_id")
            bot_msg.error_details = None

        elif result is None:
            bot_msg.status = "simulated"

        else:
            bot_msg.status = "failed"
            bot_msg.error_details = result.get("error", "WhatsApp API failed")

        db.commit()

    return {
        "contact_id": contact.id,
        "user_message_id": user_msg.id,
        "bot_reply": bot_msg.text if bot_msg else None,
        "sources": sources,
        "lead_info": lead_info
    }


# -------------------------------------------------------------
# WhatsApp Admin Panel Endpoints (Live Traffic, Reply, Simulator)
# -------------------------------------------------------------
@app.get("/api/whatsapp/contacts")
def get_whatsapp_contacts(search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(WhatsAppContact)
    if search:
        query = query.filter(
            (WhatsAppContact.name.ilike(f"%{search}%")) |
            (WhatsAppContact.phone_number.ilike(f"%{search}%")) |
            (WhatsAppContact.last_message.ilike(f"%{search}%"))
        )
    contacts = query.order_by(WhatsAppContact.last_message_at.desc().nullslast()).all()

    results = []
    for c in contacts:
        lead = db.query(Lead).filter(Lead.id == c.lead_id).first() if c.lead_id else None
        results.append({
            "id": c.id,
            "phone_number": c.phone_number,
            "name": c.name,
            "status": c.status,
            "ai_mode": c.ai_mode,
            "unread_count": c.unread_count or 0,
            "last_message": c.last_message,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
            "lead": {
                "id": lead.id,
                "service": lead.service,
                "priority": lead.priority,
                "score": lead.lead_score,
                "email": lead.email
            } if lead else None
        })
    return results


@app.get("/api/whatsapp/contacts/{contact_id}/messages")
def get_contact_messages(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(WhatsAppContact).filter(WhatsAppContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Mark as read
    contact.unread_count = 0
    db.commit()

    messages = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.contact_id == contact_id
    ).order_by(WhatsAppMessage.created_at.asc()).all()

    res = []
    for m in messages:
        sources_list = []
        if m.rag_sources:
            try:
                sources_list = json.loads(m.rag_sources)
            except Exception:
                sources_list = []

        res.append({
            "id": m.id,
            "sender": m.sender,
            "sender_name": m.sender_name,
            "text": m.text,
            "status": m.status,
            "rag_sources": sources_list,
            "created_at": m.created_at.strftime("%H:%M") if m.created_at else ""
        })
    return res


@app.post("/api/whatsapp/contacts/{contact_id}/reply")
def send_admin_reply(
    contact_id: int,
    req: ReplyRequest,
    db: Session = Depends(get_db)
):
    """Send an admin reply and record the Meta message ID."""

    contact = db.query(WhatsAppContact).filter(
        WhatsAppContact.id == contact_id
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    message_text = req.text.strip()

    if not message_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    new_msg = WhatsAppMessage(
        contact_id=contact.id,
        sender="agent",
        sender_name="Admin Agent",
        text=message_text,
        status="pending"
    )

    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)

    result = send_whatsapp_cloud_api_message(
        contact.phone_number,
        message_text
    )

    if result is not None and result.get("success"):
        new_msg.status = "sent"
        new_msg.whatsapp_message_id = result.get("message_id")
        new_msg.error_details = None
        result_message = "Message accepted by Meta API"

    elif result is None:
        new_msg.status = "simulated"
        result_message = "Simulation only: Meta credentials are missing"

    else:
        new_msg.status = "failed"
        new_msg.error_details = result.get("error")
        result_message = "Meta rejected or failed the message"

    contact.last_message = message_text
    contact.last_message_at = datetime.datetime.utcnow()

    db.commit()
    db.refresh(new_msg)

    return {
        "success": result is not None and result.get("success", False),
        "message": {
            "id": new_msg.id,
            "whatsapp_message_id": new_msg.whatsapp_message_id,
            "sender": new_msg.sender,
            "sender_name": new_msg.sender_name,
            "text": new_msg.text,
            "status": new_msg.status,
            "created_at": new_msg.created_at.strftime("%H:%M")
        },
        "detail": result_message
    }

@app.patch("/api/whatsapp/contacts/{contact_id}/toggle-ai")
def toggle_ai_mode(contact_id: int, db: Session = Depends(get_db)):
    """Toggle between AI Auto-Pilot and Human Takeover mode for a specific chat."""
    contact = db.query(WhatsAppContact).filter(WhatsAppContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact.ai_mode = "human" if contact.ai_mode == "auto" else "auto"
    db.commit()
    return {"id": contact.id, "ai_mode": contact.ai_mode}


@app.delete("/api/whatsapp/contacts/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(WhatsAppContact).filter(WhatsAppContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"message": "Contact deleted successfully"}


@app.post("/api/whatsapp/simulate")
def simulate_whatsapp_incoming(req: SimulateMessageRequest, db: Session = Depends(get_db)):
    """Simulate an incoming WhatsApp message to test the RAG engine immediately in the interface."""
    result = _process_incoming_whatsapp_message(
        phone=req.phone.strip(),
        customer_name=req.name.strip() if req.name else "WhatsApp User",
        message_text=req.text.strip(),
        db=db
    )
    return {"success": True, "result": result}


# -------------------------------------------------------------
# RAG Knowledge Base Management APIs
# -------------------------------------------------------------
@app.get("/api/rag/documents")
def list_knowledge_documents(db: Session = Depends(get_db)):
    docs = db.query(KnowledgeDocument).order_by(KnowledgeDocument.id.asc()).all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "category": d.category,
            "content": d.content,
            "tags": d.tags,
            "is_active": d.is_active,
            "created_at": d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else ""
        }
        for d in docs
    ]


@app.post("/api/rag/documents")
def create_knowledge_document(doc: KnowledgeDocCreate, db: Session = Depends(get_db)):
    new_doc = KnowledgeDocument(
        title=doc.title.strip(),
        category=doc.category.strip(),
        content=doc.content.strip(),
        tags=doc.tags.strip() if doc.tags else "",
        is_active=True
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return {"message": "Document added to Knowledge Base", "document": new_doc}


@app.put("/api/rag/documents/{doc_id}")
def update_knowledge_document(doc_id: int, doc: KnowledgeDocUpdate, db: Session = Depends(get_db)):
    existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")

    existing.title = doc.title.strip()
    existing.category = doc.category.strip()
    existing.content = doc.content.strip()
    existing.tags = doc.tags.strip() if doc.tags else ""
    existing.is_active = doc.is_active if doc.is_active is not None else existing.is_active

    db.commit()
    db.refresh(existing)
    return {"message": "Document updated", "document": existing}


@app.delete("/api/rag/documents/{doc_id}")
def delete_knowledge_document(doc_id: int, db: Session = Depends(get_db)):
    existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(existing)
    db.commit()
    return {"message": "Document deleted"}


@app.post("/api/rag/test")
def test_rag_query(req: RAGTestRequest, db: Session = Depends(get_db)):
    """Test RAG retrieval and response generation live."""
    docs = RAGEngine.retrieve_relevant_documents(req.query, db)
    resp, sources = RAGEngine.generate_grounded_response(req.query, docs, "Tester")
    return {
        "query": req.query,
        "retrieved_count": len(docs),
        "documents": docs,
        "sample_response": resp,
        "sources": sources
    }


# -------------------------------------------------------------
# Analytics & Traffic Overview API
# -------------------------------------------------------------
@app.get("/api/whatsapp/analytics")
def get_analytics(db: Session = Depends(get_db)):
    total_contacts = db.query(WhatsAppContact).count()
    total_messages = db.query(WhatsAppMessage).count()
    inbound_count = db.query(WhatsAppMessage).filter(WhatsAppMessage.sender == "user").count()
    bot_count = db.query(WhatsAppMessage).filter(WhatsAppMessage.sender == "bot").count()
    agent_count = db.query(WhatsAppMessage).filter(WhatsAppMessage.sender == "agent").count()

    total_leads = db.query(Lead).count()
    hot_leads = db.query(Lead).filter(Lead.priority == "Hot").count()
    warm_leads = db.query(Lead).filter(Lead.priority == "Warm").count()
    cold_leads = db.query(Lead).filter(Lead.priority == "Cold").count()

    resolution_rate = round((bot_count / max(1, inbound_count)) * 100) if inbound_count > 0 else 95

    return {
        "total_conversations": total_contacts,
        "total_messages": total_messages,
        "inbound_messages": inbound_count,
        "bot_replies": bot_count,
        "agent_replies": agent_count,
        "resolution_rate": min(100, resolution_rate),
        "total_leads": total_leads,
        "leads_breakdown": {
            "hot": hot_leads,
            "warm": warm_leads,
            "cold": cold_leads
        }
    }