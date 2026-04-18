from sqlalchemy import Column, String, ForeignKey, Text, DateTime, Integer, Float, Boolean
from sqlalchemy.orm import relationship
import datetime
from database import Base

class Formula(Base):
    __tablename__ = "formula"

    formula_id = Column(String(50), primary_key=True)
    formula_name_vi = Column(String(200))
    formula_category = Column(String(100))
    object_tcm = Column(Text)
    function_tcm = Column(Text)
    indications = Column(Text)
    usage_tcm = Column(Text)
    data_source = Column(Text)

class TherapeuticPrinciple(Base):
    __tablename__ = "therapeuticprinciple"

    principle_id = Column(String(50), primary_key=True)
    principle_name_vi = Column(String(200))
    description = Column(Text)
    target_pathology = Column(Text)
    data_source = Column(Text)

class FormulaPrinciple(Base):
    __tablename__ = "formulaprinciple"

    formula_id = Column(String(50), ForeignKey("formula.formula_id"), primary_key=True)
    principle_id = Column(String(50), ForeignKey("therapeuticprinciple.principle_id"), primary_key=True)
    is_main = Column(Boolean, default=False)

class SyndromePattern(Base):
    __tablename__ = "syndromepattern"

    pattern_id = Column(String(50), primary_key=True)
    pattern_name_vi = Column(String(200))
    pattern_description = Column(Text)
    tcm_disease_name = Column(String(200))
    etiology_tcm = Column(Text)
    affected_meridians_organs = Column(Text)
    eight_principles = Column(Text)
    modern_diagnostic_findings = Column(Text)
    clinical_manifestations = Column(Text)
    data_source = Column(Text)

class PatternPrinciple(Base):
    __tablename__ = "patternprinciple"

    pattern_id = Column(String(50), ForeignKey("syndromepattern.pattern_id"), primary_key=True)
    principle_id = Column(String(50), ForeignKey("therapeuticprinciple.principle_id"), primary_key=True)
    condition_note = Column(String(500))
    priority_level = Column(Integer, default=0)

class Symptom(Base):
    __tablename__ = "symptom"

    symptom_id = Column(String(50), primary_key=True)
    symptom_name = Column(String(200), nullable=False)
    symptom_group = Column(String(100))

class SymptomAlias(Base):
    __tablename__ = "symptomalias"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symptom_id = Column(String(50), ForeignKey("symptom.symptom_id"))
    alias = Column(String(200), nullable=False)

class PatternSymptom(Base):
    __tablename__ = "patternsymptom"

    pattern_id = Column(String(50), ForeignKey("syndromepattern.pattern_id"), primary_key=True)
    symptom_id = Column(String(50), ForeignKey("symptom.symptom_id"), primary_key=True)
    weight = Column(Float, default=1.0)

class HerbMaterial(Base):
    __tablename__ = "herbmaterial"

    herb_id = Column(String(50), primary_key=True)
    herb_name_vi = Column(String(200))
    herb_name_latin = Column(String(200))
    nature_vi = Column(Text)
    temp_property = Column(String(100))
    yin_yang = Column(String(50))
    element_group = Column(String(100))
    category_vi = Column(String(100))
    meridian_main = Column(String(200))
    indication_vi = Column(Text)
    safety_note = Column(Text)
    data_source = Column(Text)
    image_url = Column(String(500))

class FormulaComponent(Base):
    __tablename__ = "formulacomponent"

    id = Column(Integer, primary_key=True, autoincrement=True)
    formula_id = Column(String(50), ForeignKey("formula.formula_id"))
    herb_id = Column(String(50), ForeignKey("herbmaterial.herb_id"))
    dosage_value = Column(Float)
    dosage_unit = Column(String(20))
    dosage_note = Column(String(200))

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="doctor") # admin, doctor

    history = relationship("SearchHistory", back_populates="user", cascade="all, delete-orphan")

def get_vn_time():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).replace(tzinfo=None)

class SearchHistory(Base):
    __tablename__ = "searchhistory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    query = Column(Text, nullable=False)
    created_at = Column(DateTime, default=get_vn_time)

    user = relationship("User", back_populates="history")