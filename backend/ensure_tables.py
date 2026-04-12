import os
import sys
from dotenv import load_dotenv

# Path setup to allow imports from current dir
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Load env from same dir
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'))

from database import engine
from models import Base

def create_tables():
    print("Connecting and creating tables...")
    Base.metadata.create_all(bind=engine)
    print("DONE: Tables verified/created.")

if __name__ == "__main__":
    create_tables()
