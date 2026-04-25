import hashlib
import hmac
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from .models import Player, Session
from .hashing import hash_password, needs_rehash, verify_password
from .tokens import create_access_token

_MAX_SESSIONS = 10


class AuthService:
    def __init__(self, db: DBSession):
        self.db = db

    # ---------------------------
    # Register
    # ---------------------------
    def register(self, email: str, password: str) -> Player:
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(password) > 1000:
            raise ValueError("Password too long (max 1000 chars)")
        if self.db.query(Player).filter_by(email=email).first():
            raise ValueError("Registration failed")

        player = Player(
            email=email,
            password_hash=hash_password(password),
            player_embedding="[]",
        )
        self.db.add(player)
        self.db.commit()
        self.db.refresh(player)
        return player

    # ---------------------------
    # Login
    # ---------------------------
    def login(self, email: str, password: str, device_info: str | None = None):
        player = self.db.query(Player).filter(Player.email == email).first()

        if player is None:
            raise ValueError("Invalid credentials")

        if not verify_password(password, player.password_hash):
            raise ValueError("Invalid credentials")

        # Opportunistically upgrade legacy hashes (H1)
        if needs_rehash(player.password_hash):
            player.password_hash = hash_password(password)

        # Prune expired sessions for this player (H3)
        now = datetime.utcnow()
        self.db.query(Session).filter(
            Session.player_id == player.id,
            Session.expires_at.isnot(None),
            Session.expires_at < now,
        ).delete(synchronize_session=False)

        # Cap concurrent active sessions at _MAX_SESSIONS (H3)
        active = (
            self.db.query(Session)
            .filter(Session.player_id == player.id)
            .order_by(Session.created_at.asc())
            .all()
        )
        if len(active) >= _MAX_SESSIONS:
            for old in active[: len(active) - _MAX_SESSIONS + 1]:
                self.db.delete(old)

        # 1. create session_id manually BEFORE DB insert
        import uuid

        session_id = str(uuid.uuid4())

        # 2. create JWT using this session_id
        token = create_access_token(
            player_id=str(player.id),
            session_id=session_id,
        )

        # 3. hash token
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # 4. create DB session WITH token_hash already set
        session = Session(
            id=session_id,
            player_id=player.id,
            token_hash=token_hash,
            device_info=device_info or "",
        )

        self.db.add(session)
        self.db.commit()

        return token, player

    # ---------------------------
    # Validate session
    # ---------------------------
    def get_player_by_session(self, session_id: str, token: str) -> Player | None:
        session = self.db.query(Session).filter_by(id=session_id).first()
        if not session:
            return None

        # Fail-closed: treat missing expiry as expired (M1)
        if session.expires_at is None or session.expires_at < datetime.utcnow():
            return None

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        if not hmac.compare_digest(token_hash, session.token_hash or ""):
            return None

        return session.player

    # ---------------------------
    # Change password
    # ---------------------------
    def change_password(self, player: Player, current_password: str, new_password: str) -> None:
        if len(current_password) > 1000:
            raise ValueError("Password too long (max 1000 chars)")
        if not verify_password(current_password, player.password_hash):
            raise ValueError("Current password is incorrect")
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters")
        if len(new_password) > 1000:
            raise ValueError("Password too long (max 1000 chars)")
        player.password_hash = hash_password(new_password)
        # Revoke all sessions so stolen tokens can't be reused after a password change (H2)
        self.db.query(Session).filter(
            Session.player_id == player.id
        ).delete(synchronize_session=False)
        self.db.commit()

    # ---------------------------
    # Logout
    # ---------------------------
    def logout(self, session_id: str):
        self.db.query(Session).filter_by(id=session_id).delete()
        self.db.commit()
