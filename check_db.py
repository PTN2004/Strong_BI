from api.database import get_session_factory
from api.auth.models import User

SessionLocal = get_session_factory()
with SessionLocal() as db:
    users = db.query(User).all()
    for u in users:
        print(f"User: {u.email}, model: {u.llm_model}, provider: {u.llm_provider}")
