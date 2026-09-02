from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy.orm import scoped_session, sessionmaker
from config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)

db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session))

def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session

def create_db():
    SQLModel.metadata.create_all(engine)
