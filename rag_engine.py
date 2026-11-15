import re
import json
import math
import os
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from models import KnowledgeDocument, Lead, WhatsAppContact
from ai_agent import calculate_lead_score, calculate_priority
from automation import send_lead_to_n8n

# Default seed knowledge base items
DEFAULT_KNOWLEDGE = [
    {
        "title": "AI Automation Solutions & Workflows",
        "category": "services",
        "tags": "ai, automation, n8n, workflows, leads, bot, integration",
        "content": (
            "LeadFlow AI specializes in end-to-end AI automation. We build custom multi-agent systems, "
            "n8n webhook automations, automated WhatsApp lead qualifiers, CRM sync (HubSpot, Salesforce, Notion), "
            "and automated follow-up sequences. Our AI bots handle 24/7 inquiries, qualify leads using custom scoring rules, "
            "and save companies an average of 25+ hours of manual work every week."
        )
    },
    {
        "title": "Website Development & Custom Web Apps",
        "category": "services",
        "tags": "website, web development, frontend, backend, fastapi, react, ui/ux",
        "content": (
            "We build high-converting landing pages, modern SaaS web applications, and customer portals. "
            "Our technology stack includes FastAPI, Python, React, Tailwind CSS, PostgreSQL, and cloud deployments. "
            "All web projects are mobile-first, ultra-fast (sub-second load times), SEO optimized, and include "
            "built-in analytics and lead-capture forms. Delivery timeline is usually 1 to 3 weeks."
        )
    },
    {
        "title": "Pricing Plans & Packages",
        "category": "pricing",
        "tags": "pricing, cost, price, plans, starter, pro, enterprise, quote",
        "content": (
            "LeadFlow AI offers 3 flexible pricing tiers:\n"
            "1. Starter Automation ($299/month / ₹24,999): Single WhatsApp AI chatbot, automated CRM lead capture, up to 1,000 conversations/mo.\n"
            "2. Growth / Pro Plan ($599/month / ₹49,999): Full RAG AI knowledge retrieval, n8n multi-step workflows, custom WhatsApp admin dashboard, multi-agent lead scoring, up to 10,000 conversations/mo.\n"
            "3. Enterprise Custom: Dedicated architecture, on-premise or cloud hosting, custom LLM fine-tuning, SLA support, and custom integrations. Contact our sales team for bespoke quotes."
        )
    },
    {
        "title": "How LeadFlow AI RAG Chatbot Works",
        "category": "faq",
        "tags": "how it works, process, setup, onboarding, rag, retrieval",
        "content": (
            "Getting started with LeadFlow AI takes less than 24 hours:\n"
            "Step 1: Upload or input your business data (services, pricing, FAQs, policies) into the Knowledge Base.\n"
            "Step 2: Connect your WhatsApp number via Meta Cloud API or test with our built-in simulator.\n"
            "Step 3: The RAG engine automatically retrieves the most relatable data chunks and answers WhatsApp users 24/7 with human-like precision.\n"
            "Step 4: You can monitor all traffic in real time from the Admin Panel, view RAG context sources, or jump in with human replies anytime."
        )
    },
    {
        "title": "Contact Details, Support & Consultation Booking",
        "category": "support",
        "tags": "contact, phone, email, support, hours, consultation, demo, talk",
        "content": (
            "Our human support and consulting team is active Monday through Saturday, 9:00 AM to 7:00 PM IST. "
            "Our automated AI WhatsApp bot operates 24/7/365 without downtime.\n"
            "Direct Email: contact@leadflowai.com\n"
            "Direct WhatsApp / Call: +1 (555) 019-2834\n"
            "You can book a free 30-minute AI strategy consultation call through our website or right here in this chat by leaving your name and email."
        )
    },
    {
        "title": "Refund Policy & Guarantees",
        "category": "policies",
        "tags": "refund, guarantee, trial, terms, cancel",
        "content": (
            "We offer a 14-day 100% money-back guarantee on all our standard monthly automation plans. "
            "If our AI automation system does not save your team at least 15 hours of manual work within the first month, "
            "we provide a full refund, no questions asked. Plans can be paused or cancelled anytime with 1-click."
        )
    }
]


def seed_default_knowledge(db: Session):
    """Seed default knowledge base articles if the table is empty."""
    count = db.query(KnowledgeDocument).count()
    if count == 0:
        for item in DEFAULT_KNOWLEDGE:
            doc = KnowledgeDocument(
                title=item["title"],
                category=item["category"],
                tags=item["tags"],
                content=item["content"],
                is_active=True
            )
            db.add(doc)
        db.commit()


def _tokenize(text: str) -> List[str]:
    """Tokenize and clean words for retrieval."""
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    words = clean.split()
    stopwords = {
        "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "is",
        "it", "this", "that", "are", "was", "were", "be", "by", "of", "from", "as",
        "can", "do", "does", "did", "have", "has", "had", "i", "we", "you", "they",
        "he", "she", "what", "how", "why", "where", "when", "who", "which"
    }
    return [w for w in words if len(w) > 1 and w not in stopwords]


class RAGEngine:
    """
    Retrieval-Augmented Generation (RAG) engine for WhatsApp customer conversations.
    Retrieves relatable knowledge base chunks and generates grounded answers.
    """

    @classmethod
    def retrieve_relevant_documents(
        cls,
        query: str,
        db: Session,
        top_k: int = 3,
        min_score: float = 0.05
    ) -> List[Dict[str, Any]]:
        """
        Performs hybrid retrieval (keyword overlap + BM25-style term weighting + title boost)
        to find the most relatable knowledge documents for the incoming user query.
        """
        active_docs = db.query(KnowledgeDocument).filter(KnowledgeDocument.is_active == True).all()
        if not active_docs:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            # Fallback to general info if query is very short (like 'hi', 'hello')
            docs = active_docs[:2]
            return [
                {
                    "id": d.id,
                    "title": d.title,
                    "category": d.category,
                    "content": d.content,
                    "score": 0.1
                }
                for d in docs
            ]

        query_lower = query.lower()
        scored_docs = []

        for doc in active_docs:
            score = 0.0
            doc_title_lower = doc.title.lower()
            doc_tags_lower = (doc.tags or "").lower()
            doc_content_lower = doc.content.lower()

            # Exact phrase matches
            if len(query_lower) > 3 and query_lower in doc_content_lower:
                score += 3.0
            if len(query_lower) > 3 and query_lower in doc_title_lower:
                score += 5.0

            # Title & tags token match (high relevance)
            title_tokens = _tokenize(doc.title)
            tags_tokens = _tokenize(doc.tags or "")
            content_tokens = _tokenize(doc.content)

            # Title matches
            for token in query_tokens:
                if token in title_tokens:
                    score += 2.5
                if token in tags_tokens:
                    score += 2.0
                if token in content_tokens:
                    # BM25 frequency weighting
                    tf = content_tokens.count(token)
                    score += 1.0 + math.log(1 + tf)

            if score >= min_score:
                scored_docs.append({
                    "id": doc.id,
                    "title": doc.title,
                    "category": doc.category,
                    "content": doc.content,
                    "score": round(score, 2)
                })

        # Sort descending by score
        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        return scored_docs[:top_k]

    @classmethod
    def generate_grounded_response(
        cls,
        user_message: str,
        retrieved_docs: List[Dict[str, Any]],
        contact_name: str = "there"
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Synthesizes a helpful, relatable WhatsApp response based strictly on the retrieved knowledge base data.
        Returns (response_text, sources_metadata).
        """
        clean_name = contact_name if contact_name and contact_name.lower() != "whatsapp user" else "there"
        msg_lower = user_message.strip().lower()

        # Handle greetings
        if msg_lower in ["hi", "hello", "hey", "hola", "namaste", "good morning", "good evening", "start"]:
            greeting_resp = (
                f"👋 Hello {clean_name}! Welcome to *LeadFlow AI*.\n\n"
                "I am your automated AI assistant powered by our Knowledge Base. "
                "I can assist you with:\n"
                "• ⚡ *AI Automation & n8n Workflows*\n"
                "• 🌐 *Custom Website & Web App Development*\n"
                "• 💰 *Pricing & Custom Packages*\n"
                "• 📅 *Booking a 30-min Strategy Consultation*\n\n"
                "How can I help you today? Feel free to ask any question!"
            )
            return greeting_resp, [{"title": "Welcome Menu", "category": "general", "score": 1.0}]

        # If no relatable docs matched
        if not retrieved_docs or (len(retrieved_docs) == 1 and retrieved_docs[0]["score"] < 0.2):
            fallback_resp = (
                f"Hello {clean_name}! Thank you for reaching out to *LeadFlow AI*.\n\n"
                "I don't have the exact relatable information on that specific topic in my current knowledge base, "
                "but I've notified our team! You can also ask me about:\n"
                "• *Our AI Automation & LeadFlow services*\n"
                "• *Web development packages & tech stack*\n"
                "• *Pricing tiers & 14-day refund policy*\n\n"
                "Or simply reply with your requirements and contact email, and one of our specialists will reach out!"
            )
            return fallback_resp, []

        # Ground response using top retrieved knowledge chunks
        primary = retrieved_docs[0]
        sources = [
            {"id": d["id"], "title": d["title"], "category": d["category"], "score": d["score"]}
            for d in retrieved_docs
        ]

        # Natural grounding formulation
        paragraphs = []
        paragraphs.append(f"Hello {clean_name}! Here is the information regarding *{primary['title']}*:\n")

        # Synthesize primary content
        content_lines = [line.strip() for line in primary["content"].split("\n") if line.strip()]
        for line in content_lines:
            if line.startswith(("1.", "2.", "3.", "•", "-")):
                paragraphs.append(f"{line}")
            else:
                paragraphs.append(f"{line}")

        # If there is secondary relatable document, add concise takeaway
        if len(retrieved_docs) > 1 and retrieved_docs[1]["score"] >= 1.5:
            secondary = retrieved_docs[1]
            paragraphs.append(f"\n💡 *Related ({secondary['title']})*: {secondary['content'][:180]}...")

        paragraphs.append(
            "\n💬 Would you like to get a customized quote or schedule a quick consultation call? "
            "Just reply with your name and email!"
        )

        return "\n".join(paragraphs), sources

    @classmethod
    def check_and_extract_lead(
        cls,
        user_message: str,
        phone_number: str,
        contact_name: str,
        db: Session,
        contact: WhatsAppContact
    ) -> Dict[str, Any]:
        """
        Detects if the user is submitting contact details or requesting a service quote/call,
        and automatically creates a Lead in the system and triggers n8n.
        """
        # Look for email pattern
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', user_message)
        email = email_match.group(0) if email_match else None

        # Look for service indicators
        service = "General Inquiry"
        msg_lower = user_message.lower()
        if "ai" in msg_lower or "automation" in msg_lower or "bot" in msg_lower or "workflow" in msg_lower:
            service = "AI Automation"
        elif "web" in msg_lower or "site" in msg_lower or "app" in msg_lower or "design" in msg_lower:
            service = "Website Development"
        elif "pricing" in msg_lower or "cost" in msg_lower or "quote" in msg_lower:
            service = "Pricing & Quote"
        elif "call" in msg_lower or "demo" in msg_lower or "meeting" in msg_lower:
            service = "Consultation Demo"

        # Check if message has lead-intent indicators
        intent_signals = [
            "quote", "interested", "need", "want", "hire", "consultation",
            "demo", "cost", "price", "start", "book", "call me", "contact me"
        ]
        has_intent = any(sig in msg_lower for sig in intent_signals)

        if email or (has_intent and len(user_message.split()) >= 4):
            # Check if this contact already has a registered lead
            lead = None
            if contact.lead_id:
                lead = db.query(Lead).filter(Lead.id == contact.lead_id).first()

            lead_name = contact_name if contact_name and contact_name != "WhatsApp User" else f"WhatsApp Lead ({phone_number})"
            lead_email = email if email else f"{phone_number.replace('+', '')}@whatsapp.leadflow"

            if not lead:
                score = calculate_lead_score(lead_name, lead_email, service)
                priority = calculate_priority(score)

                new_lead = Lead(
                    name=lead_name,
                    email=lead_email,
                    phone=phone_number,
                    service=service,
                    status="New (WhatsApp)",
                    lead_score=score,
                    priority=priority
                )
                db.add(new_lead)
                db.commit()
                db.refresh(new_lead)

                # Link to contact
                contact.lead_id = new_lead.id
                db.commit()

                # Dispatch to n8n automation
                try:
                    send_lead_to_n8n(new_lead)
                except Exception as e:
                    print("n8n dispatch error:", e)

                return {
                    "lead_created": True,
                    "lead_id": new_lead.id,
                    "priority": priority,
                    "score": score,
                    "service": service
                }
            else:
                # Update existing lead service if more specific
                if service != "General Inquiry":
                    lead.service = service
                    lead.lead_score = calculate_lead_score(lead.name, lead.email, service)
                    lead.priority = calculate_priority(lead.lead_score)
                    db.commit()

        return {"lead_created": False}
