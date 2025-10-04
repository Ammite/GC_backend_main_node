from dotenv import load_dotenv
import os


load_dotenv()

# database
DATABASE_URL = os.getenv("DB_URL", "sqlite:///./database/database_files/test.db")


# security
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# api token
API_VALID_TOKEN = os.getenv("API_VALID_TOKEN")

# iiko Cloud API
IIKO_CLOUD_API_URL = os.getenv("IIKO_CLOUD_API_URL")
IIKO_CLOUD_LOGIN = os.getenv("IIKO_LOGIN_KEY")  # apiLogin для Cloud API

# iiko Server API
IIKO_SERVER_API_URL = os.getenv("IIKO_SERVER_API_URL")
IIKO_SERVER_LOGIN = os.getenv("IIKO_SERVER_LOGIN")  # логин для Server API
IIKO_SERVER_PASSWORD = os.getenv("IIKO_SERVER_PASSWORD")
