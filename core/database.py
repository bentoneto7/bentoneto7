import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

import config


@contextmanager
def get_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT,
                followers INTEGER DEFAULT 0,
                following INTEGER DEFAULT 0,
                bio TEXT,
                is_private BOOLEAN DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_scraped_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shortcode TEXT UNIQUE NOT NULL,
                account_username TEXT NOT NULL,
                caption TEXT,
                hashtags TEXT DEFAULT '[]',
                post_type TEXT NOT NULL,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                engagement_rate REAL DEFAULT 0,
                posted_at TIMESTAMP,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                url TEXT,
                FOREIGN KEY (account_username) REFERENCES accounts(username)
            );

            CREATE TABLE IF NOT EXISTS generated_ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                suggested_format TEXT,
                suggested_hashtags TEXT DEFAULT '[]',
                reasoning TEXT,
                based_on_accounts TEXT DEFAULT '[]',
                is_saved BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_posts_account ON posts(account_username);
            CREATE INDEX IF NOT EXISTS idx_posts_posted_at ON posts(posted_at);
            CREATE INDEX IF NOT EXISTS idx_posts_engagement ON posts(engagement_rate);
        """)


# --- Accounts ---

def add_account(username: str) -> bool:
    username = username.strip().lstrip("@")
    with get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO accounts (username) VALUES (?)",
                (username,)
            )
            return True
        except sqlite3.IntegrityError:
            return False


def remove_account(username: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM posts WHERE account_username = ?", (username,))
        conn.execute("DELETE FROM accounts WHERE username = ?", (username,))


def get_accounts() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM accounts ORDER BY added_at DESC").fetchall()
        return [dict(row) for row in rows]


def update_account_info(username: str, full_name: str, followers: int,
                        following: int, bio: str, is_private: bool):
    with get_connection() as conn:
        conn.execute("""
            UPDATE accounts
            SET full_name = ?, followers = ?, following = ?, bio = ?,
                is_private = ?, last_scraped_at = ?
            WHERE username = ?
        """, (full_name, followers, following, bio, is_private,
              datetime.now().isoformat(), username))


# --- Posts ---

def upsert_post(post_data: dict):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO posts (shortcode, account_username, caption, hashtags,
                             post_type, likes, comments, engagement_rate,
                             posted_at, scraped_at, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(shortcode) DO UPDATE SET
                likes = excluded.likes,
                comments = excluded.comments,
                engagement_rate = excluded.engagement_rate,
                scraped_at = excluded.scraped_at
        """, (
            post_data["shortcode"],
            post_data["account_username"],
            post_data.get("caption", ""),
            json.dumps(post_data.get("hashtags", [])),
            post_data["post_type"],
            post_data.get("likes", 0),
            post_data.get("comments", 0),
            post_data.get("engagement_rate", 0),
            post_data.get("posted_at"),
            datetime.now().isoformat(),
            post_data.get("url", ""),
        ))


def get_posts(account_username: str = None, days: int = None,
              post_type: str = None, limit: int = None,
              order_by: str = "posted_at DESC") -> list[dict]:
    query = "SELECT * FROM posts WHERE 1=1"
    params = []

    if account_username:
        query += " AND account_username = ?"
        params.append(account_username)
    if days:
        query += " AND posted_at >= datetime('now', ?)"
        params.append(f"-{days} days")
    if post_type:
        query += " AND post_type = ?"
        params.append(post_type)

    query += f" ORDER BY {order_by}"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["hashtags"] = json.loads(d["hashtags"]) if d["hashtags"] else []
            results.append(d)
        return results


def get_post_count() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]


# --- Ideas ---

def save_ideas(ideas: list[dict], based_on_accounts: list[str]):
    with get_connection() as conn:
        for idea in ideas:
            conn.execute("""
                INSERT INTO generated_ideas
                (title, description, suggested_format, suggested_hashtags,
                 reasoning, based_on_accounts)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                idea.get("title", ""),
                idea.get("description", ""),
                idea.get("suggested_format", ""),
                json.dumps(idea.get("suggested_hashtags", [])),
                idea.get("reasoning", ""),
                json.dumps(based_on_accounts),
            ))


def get_ideas(saved_only: bool = False) -> list[dict]:
    query = "SELECT * FROM generated_ideas"
    if saved_only:
        query += " WHERE is_saved = 1"
    query += " ORDER BY created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["suggested_hashtags"] = json.loads(d["suggested_hashtags"]) if d["suggested_hashtags"] else []
            d["based_on_accounts"] = json.loads(d["based_on_accounts"]) if d["based_on_accounts"] else []
            results.append(d)
        return results


def toggle_idea_saved(idea_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE generated_ideas SET is_saved = NOT is_saved WHERE id = ?",
            (idea_id,)
        )
