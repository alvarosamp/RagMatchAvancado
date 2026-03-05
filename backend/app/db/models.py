from sqlalchemy import JSON, Column, Integer, String, ForeignKey 
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship
Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String, unique=True, index=True)  # ex: "TL-SG3210"
    category = Column(String)  # ex: "switch"
    data = Column(JSON)  # specs do produto
    matching_results = relationship("MatchingResult", back_populates="product")
    
class MatchingResult(Base):
    __tablename__ = "matching_results"
    
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String)
    details = Column(String)
    product_id = Column(Integer, ForeignKey("products.id"))
    requirements_id = Column(Integer, ForeignKey("requirements.id"))
    
    product = relationship("Product", back_populates="matching_results")
    requirement = relationship("Requirement", back_populates="matching_results")