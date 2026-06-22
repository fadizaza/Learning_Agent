import hashlib
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "learning.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            grade TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            topic TEXT NOT NULL,
            level TEXT NOT NULL,
            goals TEXT DEFAULT '',
            syllabus TEXT,
            language TEXT DEFAULT 'ar',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            module_index INTEGER NOT NULL,
            module_title TEXT NOT NULL,
            completed BOOLEAN DEFAULT 0,
            score REAL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            module_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            module_index INTEGER NOT NULL,
            questions TEXT,
            answers TEXT,
            score REAL,
            feedback TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS lesson_cache (
            content_hash TEXT NOT NULL,
            module_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            PRIMARY KEY (content_hash, module_index)
        );
    """)
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN grade TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN subject TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN goals TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN content_hash TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN language TEXT DEFAULT 'ar'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def compute_content_hash(grade: str, subject: str, topic: str, level: str, goals: str, language: str = "ar") -> str:
    key = f"{grade}|{subject}|{topic}|{level}|{goals}|{language}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def find_syllabus_by_content_hash(content_hash: str, grade="", subject="", topic="", level="", goals="", language="ar"):
    conn = get_connection()
    row = conn.execute(
        "SELECT syllabus FROM sessions WHERE content_hash = ? AND syllabus IS NOT NULL LIMIT 1",
        (content_hash,),
    ).fetchone()
    if row:
        conn.close()
        return json.loads(row["syllabus"])
    if grade:
        row2 = conn.execute(
            "SELECT id, syllabus FROM sessions WHERE grade=? AND subject=? AND topic=? AND level=? AND goals=? AND language=? AND syllabus IS NOT NULL LIMIT 1",
            (grade, subject, topic, level, goals, language),
        ).fetchone()
        if row2:
            conn.execute(
                "UPDATE sessions SET content_hash=? WHERE id=?",
                (content_hash, row2["id"]),
            )
            conn.commit()
            conn.close()
            return json.loads(row2["syllabus"])
        conn.close()
        return None
    conn.close()
    return None


def create_session(session_id: str, grade: str, subject: str, topic: str, level: str, goals: str, syllabus: str, content_hash: str = "", language: str = "ar"):
    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (id, grade, subject, topic, level, goals, syllabus, content_hash, language) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, grade, subject, topic, level, goals, syllabus, content_hash, language),
    )
    conn.commit()
    conn.close()


def get_session(session_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def init_progress(session_id: str, modules: list):
    conn = get_connection()
    for i, mod in enumerate(modules):
        conn.execute(
            "INSERT INTO progress (session_id, module_index, module_title) VALUES (?, ?, ?)",
            (session_id, i, mod["title"]),
        )
    conn.commit()
    conn.close()


def get_progress(session_id: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM progress WHERE session_id = ? ORDER BY module_index", (session_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def complete_module(session_id: str, module_index: int, score: float):
    conn = get_connection()
    conn.execute(
        "UPDATE progress SET completed = 1, score = ? WHERE session_id = ? AND module_index = ?",
        (score, session_id, module_index),
    )
    conn.commit()
    conn.close()


def save_lesson(session_id: str, module_index: int, content: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO lessons (session_id, module_index, content) VALUES (?, ?, ?)",
        (session_id, module_index, content),
    )
    conn.commit()
    conn.close()


def get_cached_lesson(session_id: str, module_index: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT content FROM lessons WHERE session_id = ? AND module_index = ?",
        (session_id, module_index),
    ).fetchone()
    conn.close()
    return json.loads(row["content"]) if row else None


def save_lesson_to_cache(lesson_cache_key: str, module_index: int, content: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO lesson_cache (content_hash, module_index, content) VALUES (?, ?, ?)",
        (lesson_cache_key, module_index, content),
    )
    conn.commit()
    conn.close()


def find_cached_lesson_by_params(grade, subject, topic, level, goals, module_index, language="ar"):
    conn = get_connection()
    row = conn.execute(
        """SELECT l.content FROM lessons l
           JOIN sessions s ON l.session_id = s.id
           WHERE s.grade=? AND s.subject=? AND s.topic=? AND s.level=? AND s.goals=? AND s.language=?
             AND l.module_index=?
           LIMIT 1""",
        (grade, subject, topic, level, goals, language, module_index),
    ).fetchone()
    conn.close()
    return json.loads(row["content"]) if row else None


def get_cached_lesson_by_content(lesson_cache_key: str, module_index: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT content FROM lesson_cache WHERE content_hash = ? AND module_index = ?",
        (lesson_cache_key, module_index),
    ).fetchone()
    conn.close()
    return json.loads(row["content"]) if row else None


def save_quiz_attempt(session_id: str, module_index: int, questions: str, answers: str, score: float, feedback: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO quiz_attempts (session_id, module_index, questions, answers, score, feedback) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, module_index, questions, answers, score, feedback),
    )
    conn.commit()
    conn.close()
