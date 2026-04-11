from sqlalchemy import Column, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
import datetime
from database import Base
from sqlalchemy import Integer

class Formula(Base):
    __tablename__ = "Formula"

    formula_id = Column(String, primary_key=True)
    formula_name_vi = Column(String)
    formula_category = Column(String)
    indications = Column(Text)

class TherapeuticPrinciple(Base):
    __tablename__ = "TherapeuticPrinciple"

    principle_id = Column(String, primary_key=True)
    principle_name_vi = Column(String)

class FormulaPrinciple(Base):
    __tablename__ = "FormulaPrinciple"

    formula_id = Column(String, ForeignKey("Formula.formula_id"), primary_key=True)
    principle_id = Column(String, ForeignKey("TherapeuticPrinciple.principle_id"), primary_key=True)

class SyndromePattern(Base):
    __tablename__ = "SyndromePattern"

    pattern_id = Column(String, primary_key=True)
    pattern_name_vi = Column(String)
    clinical_manifestations = Column(Text)

class PatternPrinciple(Base):
    __tablename__ = "PatternPrinciple"

    pattern_id = Column(String, ForeignKey("SyndromePattern.pattern_id"), primary_key=True)
    principle_id = Column(String, ForeignKey("TherapeuticPrinciple.principle_id"), primary_key=True)

    condition_note = Column(String)
    priority_level = Column(Integer)   # 👈 THÊM DÒNG NÀY

class User(Base):
    __tablename__ = "Users"

    user_id = Column(String(36), primary_key=True)
    username = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(String(20), default="doctor") # role có thể là admin, doctor

class SearchHistory(Base):
    __tablename__ = "SearchHistory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("Users.user_id"))
    query = Column(String(500))
    timestamp = Column(DateTime, default=datetime.datetime.now)

    user = relationship("User")