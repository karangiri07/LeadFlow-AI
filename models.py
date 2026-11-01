
from sqlalchemy import Column, Integer, String
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
