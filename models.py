from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.mysql import BIGINT
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

class Server(Base):
    __tablename__ = 'servers'
    id = Column(Integer, primary_key=True)
    server_id = Column(BIGINT(unsigned=True), unique=True)
    
    # if your server name has more than 100 chars tough luck
    name = Column(String(100))
    muted_role_id = Column(Integer)
    unmuted_role_id = Column(Integer)


class Mute(Base):
    __tablename__ = 'mutes'
    id = Column(Integer, primary_key=True)

    server_id = Column(BIGINT(unsigned=True))
    muted_id = Column(Integer)
    muter_id = Column(Integer)
    channel_id = Column(Integer)
    expiration_time = Column(DateTime)
