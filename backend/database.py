import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Fallback to local sqlite for dev if no env var is found, or just local sql server
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "mssql+pyodbc://admin1:Tomato%402004@localhost/YHCT_Recommender?driver=ODBC+Driver+17+for+SQL+Server&MultipleActiveResultSets=True"
)

# Fix for postgresql URL format issue (PostgreSQL >= 14 sometimes requires postgresql:// instead of postgres://)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
