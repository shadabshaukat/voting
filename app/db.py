from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# Configure SQLAlchemy engine with tuned pooling options (env-configurable)
from sqlalchemy.pool import QueuePool

pool_kwargs = {
    "pool_pre_ping": settings.DB_POOL_PRE_PING,
    "pool_recycle": settings.DB_POOL_RECYCLE,
}

poolclass = None
_poolclass_cfg = (settings.DB_POOLCLASS or "QueuePool").lower()
if _poolclass_cfg == "queuepool":
    poolclass = QueuePool
    pool_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_POOL_MAX_OVERFLOW,
        "pool_use_lifo": settings.DB_POOL_USE_LIFO,
    })
elif _poolclass_cfg == "nullpool":
    from sqlalchemy.pool import NullPool
    poolclass = NullPool

engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    poolclass=poolclass,  # None means default QueuePool
    **pool_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Proper DB dependency for FastAPI (avoids 422 from sessionmaker signature)
# Usage: db_session: Session = Depends(db.get_db)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base = declarative_base()