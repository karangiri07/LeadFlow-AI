import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), nullable=False)
    phone = Column(String(20), nullable=True)
    service = Column(String(150), nullable=False)
    status = Column(String(50), default="New")
    lead_score = Column(Integer, default=0)
    priority = Column(String(20), default="Cold")


class WhatsAppContact(Base):
    __tablename__ = "whatsapp_contacts"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), default="WhatsApp User")
    unread_count = Column(Integer, default=0)
    status = Column(String(50), default="active")  # active, waiting_agent, closed
    ai_mode = Column(String(50), default="auto")    # auto, human
    last_message = Column(Text, nullable=True)
    last_message_at = Column(DateTime, default=datetime.datetime.utcnow)
    lead_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    messages = relationship("WhatsAppMessage", back_populates="contact", cascade="all, delete-orphan", order_by="WhatsAppMessage.created_at")


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("whatsapp_contacts.id"), index=True, nullable=False)
    sender = Column(String(20), nullable=False)  # user, bot, agent
    sender_name = Column(String(100), nullable=True)
    text = Column(Text, nullable=False)
    status = Column(String(50), default="received")  # received, sent, delivered, read
    rag_sources = Column(Text, nullable=True)  # JSON formatted retrieved chunks
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    contact = relationship("WhatsAppContact", back_populates="messages")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(100), default="general")  # services, pricing, faq, support, company
    content = Column(Text, nullable=False)
    tags = Column(String(255), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class WhatsAppSetting(Base):
    __tablename__ = "whatsapp_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
