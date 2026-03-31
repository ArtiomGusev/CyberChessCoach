import hashlib
import hmac
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from .models import Player, Session
from .hashing import hash_password, verify_password
from .tokens import create_access_token


class AuthService:
    def __init__(self, db: DBSession):
        self.db = db

    # ---------------------------
    # Register
    # ---------------------------
    def register(self, email: str, password: str) -> Player:
        if self.db.query(Player).filter_by(email=email).first():
            raise ValueError("Email already registered")

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

        # 1️⃣ create session_id manually BEFORE DB insert
        import uuid, hashlib

        session_id = str(uuid.uuid4())

        # 2️⃣ create JWT using this session_id
        token = create_access_token(
            player_id=str(player.id),
            session_id=session_id,
        )

        # 3️⃣ hash token
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # 4️⃣ create DB session WITH token_hash already set
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

        # Defence-in-depth: reject DB sessions whose server-side expiry has passed.
        # The primary expiry gate is the JWT exp claim (15 min), checked by
        # decode_token() before this method is called.  This guard catches edge
        # cases such as clock-skew drift, manually expired sessions, or a valid
        # JWT referencing a stale DB record after SECRET_KEY rotation.
        if session.expires_at is not None and session.expires_at < datetime.utcnow():
            return None

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        if not hmac.compare_digest(token_hash, session.token_hash or ""):
            return None

        return session.player

    # ---------------------------
    # Change password
    # ---------------------------
    def change_password(self, player: Player, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, player.password_hash):
            raise ValueError("Current password is incorrect")
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters")
        player.password_hash = hash_password(new_password)
        self.db.commit()

    # ---------------------------
    # Logout
    # ---------------------------
    def logout(self, session_id: str):
        self.db.query(Session).filter_by(id=session_id).delete()
        self.db.commit()
