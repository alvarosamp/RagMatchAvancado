from sqlachemy import Column, Integer, String, JSON
from sqlalchemy.org import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String, unique=True, index=True, nullable=False)  # ex: "TL-SG3210"
    category = Column(String, index=True, nullable=False)  # ex: "switch"
    data = Column(JSON, nullable=False)  # specs do produto