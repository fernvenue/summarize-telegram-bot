# This file is used to create the database and the tables;
# We use sqlalchemy to create the database and the tables;
# We use sqlite as our database, and we use sqlalchemy to connect to the database;
from sqlalchemy import create_engine, Column, String, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from datetime import datetime

# This is the base class of the database, we need to inherit it when we create a table;
Base = declarative_base()

# Handle create datetime and update datetime with base class;
class BaseWithTimestamps:
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Here we use `anyLink` table to store the Any Link item that already summarized;
class Summarize(Base, BaseWithTimestamps):
    __tablename__ = 'anyLink'
    id = Column(String, primary_key=True, index=True)
    type = Column(String)
    summary = Column(String)
    title = Column(String)

# Here we use sqlite as our database, and we use sqlalchemy to connect to the database;
engine = create_engine('sqlite:///database.db', echo=False, pool_size=10, max_overflow=10)
# We use sessionmaker to create a session object, and we can use this object to query the database;
seesion = sessionmaker(bind=engine)

# This function is used to get the session object;
def get_session():
    return seesion()

# Create all the tables;
Base.metadata.create_all(engine)