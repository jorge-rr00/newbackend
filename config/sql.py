"""Database configuration and connection."""
import os
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import unquote

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool


SESSIONS_TABLE = "chat_sessions"
MESSAGES_TABLE = "chat_messages"
USERS_TABLE = "chat_users"
TOKENS_TABLE = "auth_tokens"

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("Missing environment variable: DATABASE_URL")

DATABASE_URL = unquote(DATABASE_URL)

_pool: Optional[SimpleConnectionPool] = None


def _get_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn=1,
            maxconn=int(os.getenv("DB_POOL_MAX", "5")),
            dsn=DATABASE_URL,
        )
    return _pool


def get_conn():
    pool = _get_pool()
    return pool.getconn()


def put_conn(conn):
    pool = _get_pool()
    pool.putconn(conn)


def init_db() -> None:
    """Initialize database tables."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {USERS_TABLE} (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                );
                """
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TOKENS_TABLE} (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES {USERS_TABLE}(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL,
                    last_seen TIMESTAMPTZ NOT NULL
                );
                """
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SESSIONS_TABLE} (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                );
                """
            )
            cur.execute(
                f"ALTER TABLE {SESSIONS_TABLE} ADD COLUMN IF NOT EXISTS user_id TEXT;"
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {MESSAGES_TABLE} (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES {SESSIONS_TABLE}(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                );
                """
            )
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{MESSAGES_TABLE}_session_id_id
                ON {MESSAGES_TABLE}(session_id, id);
                """
            )
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{SESSIONS_TABLE}_user_id
                ON {SESSIONS_TABLE}(user_id);
                """
            )
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{TOKENS_TABLE}_user_id
                ON {TOKENS_TABLE}(user_id);
                """
            )
            conn.commit()
    finally:
        put_conn(conn)


def create_user(username: str, password_hash: str) -> str:
    """Create a new user."""
    import uuid

    user_id = uuid.uuid4().hex
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            now = datetime.utcnow()
            cur.execute(
                f"INSERT INTO {USERS_TABLE} (id, username, password_hash, created_at) "
                f"VALUES (%s, %s, %s, %s)",
                (user_id, username, password_hash, now),
            )
            conn.commit()
    finally:
        put_conn(conn)
    return user_id


def get_user_by_username(username: str) -> Optional[Dict]:
    """Fetch user by username."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT id, username, password_hash, created_at "
                f"FROM {USERS_TABLE} WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        put_conn(conn)


def get_user_by_id(user_id: str) -> Optional[Dict]:
    """Fetch user by id."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT id, username, created_at FROM {USERS_TABLE} WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        put_conn(conn)


def create_auth_token(user_id: str) -> str:
    """Create a new auth token for a user."""
    import uuid

    token = uuid.uuid4().hex
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            now = datetime.utcnow()
            cur.execute(
                f"INSERT INTO {TOKENS_TABLE} (token, user_id, created_at, last_seen) "
                f"VALUES (%s, %s, %s, %s)",
                (token, user_id, now, now),
            )
            conn.commit()
    finally:
        put_conn(conn)
    return token


def revoke_auth_token(token: str) -> None:
    """Revoke an auth token."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {TOKENS_TABLE} WHERE token = %s", (token,))
            conn.commit()
    finally:
        put_conn(conn)


def get_user_by_token(token: str) -> Optional[Dict]:
    """Fetch user by auth token."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT u.id, u.username "
                f"FROM {TOKENS_TABLE} t "
                f"JOIN {USERS_TABLE} u ON u.id = t.user_id "
                f"WHERE t.token = %s",
                (token,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                f"UPDATE {TOKENS_TABLE} SET last_seen = %s WHERE token = %s",
                (datetime.utcnow(), token),
            )
            conn.commit()
            return dict(row)
    finally:
        put_conn(conn)


def create_session(user_id: str, session_id: Optional[str] = None) -> str:
    """Create a new session."""
    if not session_id:
        import uuid

        session_id = uuid.uuid4().hex

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            now = datetime.utcnow()
            cur.execute(
                f"INSERT INTO {SESSIONS_TABLE} (id, user_id, created_at) VALUES (%s, %s, %s) "
                f"ON CONFLICT (id) DO NOTHING",
                (session_id, user_id, now),
            )
            conn.commit()
    finally:
        put_conn(conn)
    return session_id


def session_exists(session_id: str, user_id: Optional[str] = None) -> bool:
    """Check if a session exists."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if user_id:
                cur.execute(
                    f"SELECT 1 FROM {SESSIONS_TABLE} WHERE id = %s AND user_id = %s",
                    (session_id, user_id),
                )
            else:
                cur.execute(f"SELECT 1 FROM {SESSIONS_TABLE} WHERE id = %s", (session_id,))
            return cur.fetchone() is not None
    finally:
        put_conn(conn)


def add_message(session_id: str, role: str, content: str) -> None:
    """Add a message to a session."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            now = datetime.utcnow()
            cur.execute(
                f"INSERT INTO {MESSAGES_TABLE} (session_id, role, content, created_at) "
                f"VALUES (%s, %s, %s, %s)",
                (session_id, role, content, now),
            )
            conn.commit()
    finally:
        put_conn(conn)


def get_recent_messages(session_id: str, limit: int = 50, user_id: Optional[str] = None) -> List[Dict]:
    """Get recent messages from a session."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if user_id:
                cur.execute(
                    f"SELECT m.id, m.role, m.content, m.created_at "
                    f"FROM {MESSAGES_TABLE} m "
                    f"JOIN {SESSIONS_TABLE} s ON s.id = m.session_id "
                    f"WHERE m.session_id = %s AND s.user_id = %s "
                    f"ORDER BY m.id DESC LIMIT %s",
                    (session_id, user_id, limit),
                )
            else:
                cur.execute(
                    f"SELECT id, role, content, created_at "
                    f"FROM {MESSAGES_TABLE} "
                    f"WHERE session_id = %s "
                    f"ORDER BY id DESC LIMIT %s",
                    (session_id, limit),
                )
            rows = cur.fetchall()
            rows = list(reversed(rows))
            return [dict(r) for r in rows]
    finally:
        put_conn(conn)


def list_sessions(user_id: str) -> List[Dict]:
    """List all sessions with metadata."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT s.id,
                       s.created_at,
                       COUNT(m.id) as message_count,
                       MAX(m.created_at) as last_message
                FROM {SESSIONS_TABLE} s
                LEFT JOIN {MESSAGES_TABLE} m ON s.id = m.session_id
                WHERE s.user_id = %s
                GROUP BY s.id
                ORDER BY COALESCE(MAX(m.created_at), s.created_at) DESC
                """,
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        put_conn(conn)


def clear_session(session_id: str, user_id: str) -> None:
    """Clear all messages from a session."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {MESSAGES_TABLE} WHERE session_id = %s AND EXISTS ("
                f"SELECT 1 FROM {SESSIONS_TABLE} s WHERE s.id = %s AND s.user_id = %s)",
                (session_id, session_id, user_id),
            )
            conn.commit()
    finally:
        put_conn(conn)


def delete_session(session_id: str, user_id: str) -> None:
    """Delete a session and its messages."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {SESSIONS_TABLE} WHERE id = %s AND user_id = %s",
                (session_id, user_id),
            )
            conn.commit()
    finally:
        put_conn(conn)


def delete_all_sessions(user_id: str) -> None:
    """Delete all sessions and messages."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {SESSIONS_TABLE} WHERE user_id = %s", (user_id,))
            conn.commit()
    finally:
        put_conn(conn)
