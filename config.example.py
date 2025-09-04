from dotenv import load_dotenv
import os


load_dotenv()

# database
DATABASE_URL = os.getenv("DB_URL", "sqlite:///./database/database_files/test.db")


# security
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30))