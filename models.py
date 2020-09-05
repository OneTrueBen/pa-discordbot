from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///db.sqlite3')
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()
Session = sessionmaker(bind = engine) 

class Quote(Base):
    __tablename__ = 'quotes'
    id = Column(Integer, primary_key=True)

    author = Column(String)
    message = Column(String)
    time_sent = Column(DateTime)
    server = Column(String)
    added_by = Column(String)
    number = Column(Integer)

class ModRole(Base):
    __tablename__ = 'modroles'
    id = Column(Integer, primary_key=True)

    server = Column(String)
    role = Column(String)
