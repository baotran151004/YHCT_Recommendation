from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "mssql+pyodbc://admin1:Tomato%402004@localhost/YHCT_Recommender?driver=ODBC+Driver+17+for+SQL+Server&MultipleActiveResultSets=True"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()