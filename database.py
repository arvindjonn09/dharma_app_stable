import os
import json
import sqlite3
import datetime

# Directories & files
# Directories & files
BOOKS_DIR = "books"
UNREADABLE_FILE = "unreadable_books.json"
FAVOURITES_FILE = "favourites.json"
PRACTICE_CANDIDATES_FILE = "practice_candidates.json"
APPROVED_PRACTICES_FILE = "approved_practices.json"

# Directories for guidance media
GUIDANCE_AUDIO_DIR = "guidance_audio"
GUIDANCE_MEDIA_DIR = "guidance_media"

os.makedirs(GUIDANCE_AUDIO_DIR, exist_ok=True)
os.makedirs(GUIDANCE_MEDIA_DIR, exist_ok=True)

SESSIONS_FILE = "sessions.json"
SESSION_TTL_MINUTES = 40

# SQLite DB for users
DB_FILE = "dharma_app.db"
GUIDANCE_AUDIO_DIR = "guidance_audio"
SESSIONS_FILE = "sessions.json"

# Session timeout (already used in your app)
SESSION_TTL_MINUTES = 40

# SQLite DB for users
DB_FILE = "dharma_app.db"

os.makedirs(GUIDANCE_AUDIO_DIR, exist_ok=True)


# ---------- SQLITE USER DB ----------

def init_db():
    """Initialise the SQLite database for user storage."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT,
                first_name TEXT,
                last_name TEXT,
                year_of_birth INTEGER,
                language TEXT,
                location TEXT,
                data TEXT
            )
            """
        )
        conn.commit()
        # Structured mantras table (deity levels 1-5 with auto sectioning)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mantras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deity_id TEXT NOT NULL,
                level_number INTEGER NOT NULL,
                section_number INTEGER NOT NULL,
                sort_order INTEGER NOT NULL,
                title TEXT,
                content TEXT,
                UNIQUE(deity_id, level_number, section_number)
            )
            """
        )
        # User progress for structured mantras
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                mantra_id INTEGER NOT NULL,
                reflection_text TEXT,
                completed_at TEXT
            )
            """
        )
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def save_user_to_db(profile: dict):
    """Insert or update a single user profile into SQLite."""
    if not profile:
        return
    username = profile.get("username")
    if not username:
        return

    password_val = profile.get("password", "")
    first_name = profile.get("first_name")
    last_name = profile.get("last_name")
    year = profile.get("year_of_birth")
    language = profile.get("language")
    location = profile.get("location")
    data_json = json.dumps(profile, ensure_ascii=False)

    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO users (
                username, password, first_name, last_name,
                year_of_birth, language, location, data
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                password_val,
                first_name,
                last_name,
                year,
                language,
                location,
                data_json,
            ),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def load_user_from_db(username: str) -> dict:
    """Load a single user profile from SQLite by username."""
    if not username:
        return {}
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT password, data FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return {}
    else:
        try:
            conn.close()
        except Exception:
            pass

    if not row:
        return {}

    password_val, data_json = row
    try:
        profile = json.loads(data_json) if data_json else {}
    except Exception:
        profile = {}

    profile.setdefault("username", username)
    if password_val:
        profile["password"] = password_val
    return profile


def load_all_users_from_db() -> dict:
    """Load all user profiles from SQLite into a dict keyed by username."""
    users = {}
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT username, data FROM users")
        rows = cur.fetchall()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return users
    else:
        try:
            conn.close()
        except Exception:
            pass

    for username, data_json in rows:
        try:
            profile = json.loads(data_json) if data_json else {}
        except Exception:
            profile = {}
        profile.setdefault("username", username)
        users[username] = profile
    return users


# Ensure DB exists
init_db()


# ---------- STRUCTURED MANTRAS (DEITY LEVELS) ----------

def _fetchall_dict(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def add_structured_mantra(deity_id: str, level_number: int, title: str, content: str):
    """
    Insert a mantra for a deity+level.
    Auto-assigns section_number and sort_order as next available.
    Returns inserted row dict or None on error.
    """
    if not deity_id or not level_number:
        return None
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(MAX(section_number), 0) FROM mantras WHERE deity_id = ? AND level_number = ?",
            (deity_id, level_number),
        )
        last_section = cur.fetchone()[0] or 0
        next_section = last_section + 1
        cur.execute(
            """
            INSERT INTO mantras (deity_id, level_number, section_number, sort_order, title, content)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (deity_id, level_number, next_section, next_section, title, content),
        )
        conn.commit()
        mantra_id = cur.lastrowid
        cur.execute(
            """
            SELECT id, deity_id, level_number, section_number, sort_order, title, content
            FROM mantras WHERE id = ?
            """,
            (mantra_id,),
        )
        row = cur.fetchone()
    except Exception:
        row = None
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if not row:
        return None
    return {
        "id": row[0],
        "deity_id": row[1],
        "level_number": row[2],
        "section_number": row[3],
        "sort_order": row[4],
        "title": row[5],
        "content": row[6],
    }


def get_next_section_and_sort(deity_id: str, level_number: int) -> int:
    """Return the next section/sort number for a deity+level (1 if none exist)."""
    if not deity_id or not level_number:
        return 1
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(MAX(section_number), 0) FROM mantras WHERE deity_id = ? AND level_number = ?",
            (deity_id, level_number),
        )
        last_section = cur.fetchone()[0] or 0
    except Exception:
        last_section = 0
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return (last_section or 0) + 1


def add_mantra(deity_id: str, level_number: int, title: str, content: str):
    """Wrapper for structured mantras to match simplified admin usage."""
    return add_structured_mantra(deity_id, level_number, title, content)


def get_deity_list_for_structured_mantras():
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT deity_id FROM mantras ORDER BY deity_id COLLATE NOCASE ASC")
        rows = cur.fetchall()
    except Exception:
        rows = []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return [r[0] for r in rows if r and r[0]]


def get_mantras_for_level(deity_id: str, level_number: int):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, deity_id, level_number, section_number, sort_order, title, content
            FROM mantras
            WHERE deity_id = ? AND level_number = ?
            ORDER BY sort_order ASC
            """,
            (deity_id, level_number),
        )
        rows = cur.fetchall()
    except Exception:
        rows = []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    results = []
    for row in rows:
        results.append(
            {
                "id": row[0],
                "deity_id": row[1],
                "level_number": row[2],
                "section_number": row[3],
                "sort_order": row[4],
                "title": row[5],
                "content": row[6],
            }
        )
    return results


def reorder_mantras_for_level(deity_id: str, level_number: int, ordered_ids):
    """Reassign sort_order and section_number according to provided ordered_ids."""
    if not ordered_ids:
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        for idx, mantra_id in enumerate(ordered_ids, start=1):
            cur.execute(
                """
                UPDATE mantras
                SET sort_order = ?, section_number = ?
                WHERE id = ? AND deity_id = ? AND level_number = ?
                """,
                (idx, idx, mantra_id, deity_id, level_number),
            )
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_next_uncompleted_mantra(user_id: str, deity_id: str):
    """
    Return (next_mantra_dict, stats_dict)
    stats: total, completed, per-level totals/completed.
    """
    if not deity_id:
        return None, {}
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        # Build stats
        cur.execute(
            """
            SELECT level_number, COUNT(*) as total
            FROM mantras
            WHERE deity_id = ?
            GROUP BY level_number
            """,
            (deity_id,),
        )
        totals = {row[0]: row[1] for row in cur.fetchall()}
        cur.execute(
            """
            SELECT m.level_number, COUNT(*) as completed_count
            FROM user_progress up
            JOIN mantras m ON m.id = up.mantra_id
            WHERE up.user_id = ? AND m.deity_id = ?
            GROUP BY m.level_number
            """,
            (user_id or "", deity_id),
        )
        completed_map = {row[0]: row[1] for row in cur.fetchall()}
        stats = {
            "totals": totals,
            "completed": completed_map,
        }
        # Next uncompleted mantra ordered by level then sort_order
        cur.execute(
            """
            SELECT m.id, m.deity_id, m.level_number, m.section_number, m.sort_order, m.title, m.content
            FROM mantras m
            LEFT JOIN user_progress up
              ON up.mantra_id = m.id AND up.user_id = ?
            WHERE m.deity_id = ? AND up.id IS NULL
            ORDER BY m.level_number ASC, m.sort_order ASC
            LIMIT 1
            """,
            (user_id or "", deity_id),
        )
        row = cur.fetchone()
    except Exception:
        row = None
        stats = {}
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if not row:
        return None, stats
    mantra = {
        "id": row[0],
        "deity_id": row[1],
        "level_number": row[2],
        "section_number": row[3],
        "sort_order": row[4],
        "title": row[5],
        "content": row[6],
    }
    return mantra, stats


def mark_mantra_completed(user_id: str, mantra_id: int, reflection_text: str) -> bool:
    """Record completion with reflection. Returns True if newly saved, False if already completed or error."""
    if not user_id or not mantra_id:
        return False
    try:
        from security_utils import encrypt_field
    except Exception:
        encrypt_field = None  # type: ignore
    enc_reflection = reflection_text.strip()
    if encrypt_field:
        try:
            enc_reflection = encrypt_field(enc_reflection)
        except Exception:
            enc_reflection = reflection_text.strip()
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        # Prevent duplicate completion for same user/mantra
        cur.execute(
            "SELECT id FROM user_progress WHERE user_id = ? AND mantra_id = ? LIMIT 1",
            (user_id, mantra_id),
        )
        if cur.fetchone():
            return False
        cur.execute(
            """
            INSERT INTO user_progress (user_id, mantra_id, reflection_text, completed_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, mantra_id, enc_reflection, datetime.datetime.now().isoformat()),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_level_progress_summary(user_id: str, deity_id: str):
    """Return dict of {level: (completed, total)}."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT level_number, COUNT(*) FROM mantras
            WHERE deity_id = ?
            GROUP BY level_number
            """,
            (deity_id,),
        )
        totals = {row[0]: row[1] for row in cur.fetchall()}
        cur.execute(
            """
            SELECT m.level_number, COUNT(*) FROM user_progress up
            JOIN mantras m ON m.id = up.mantra_id
            WHERE up.user_id = ? AND m.deity_id = ?
            GROUP BY m.level_number
            """,
            (user_id or "", deity_id),
        )
        completed = {row[0]: row[1] for row in cur.fetchall()}
    except Exception:
        totals = {}
        completed = {}
    finally:
        try:
            conn.close()
        except Exception:
            pass
    out = {}
    for lvl, tot in totals.items():
        out[lvl] = (completed.get(lvl, 0), tot)
    return out


def get_top_completed_mantras(limit: int = 10):
    """
    Return a list of most completed structured mantras with counts.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                m.id,
                m.deity_id,
                m.level_number,
                m.section_number,
                m.title,
                COUNT(up.id) AS completed_count
            FROM mantras m
            JOIN user_progress up ON up.mantra_id = m.id
            GROUP BY m.id, m.deity_id, m.level_number, m.section_number, m.title
            ORDER BY completed_count DESC, m.deity_id ASC, m.level_number ASC, m.section_number ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
    except Exception:
        rows = []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    results = []
    for row in rows:
        results.append(
            {
                "id": row[0],
                "deity_id": row[1],
                "level_number": row[2],
                "section_number": row[3],
                "title": row[4],
                "completed_count": row[5],
            }
        )
    return results


def update_structured_mantra(mantra_id: int, title: str, content: str):
    """Update title/content of a structured mantra."""
    if not mantra_id:
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE mantras
            SET title = ?, content = ?
            WHERE id = ?
            """,
            (title, content, mantra_id),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def delete_structured_mantra(mantra_id: int):
    """Delete a structured mantra by id."""
    if not mantra_id:
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("DELETE FROM mantras WHERE id = ?", (mantra_id,))
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------- SESSIONS (JSON) ----------

def load_sessions():
    """Load persistent login sessions from disk."""
    if not os.path.exists(SESSIONS_FILE):
        return {}
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception:
        return {}


def save_sessions(sessions: dict):
    """Persist login sessions to disk."""
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ---------- BOOK LIST / UNREADABLE ----------

def list_book_names():
    if not os.path.exists(BOOKS_DIR):
        return []
    files = [
        f for f in os.listdir(BOOKS_DIR)
        if f.lower().endswith((".pdf", ".epub"))
    ]
    return sorted(files)


def load_unreadable():
    if not os.path.exists(UNREADABLE_FILE):
        return {}
    try:
        with open(UNREADABLE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}
    except Exception:
        return {}


# ---------- FAVOURITES ----------

def load_favourites():
    if not os.path.exists(FAVOURITES_FILE):
        return {}
    try:
        with open(FAVOURITES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except json.JSONDecodeError:
        return {}
    except Exception:
        return {}


def save_favourites(favs: dict):
    try:
        with open(FAVOURITES_FILE, "w", encoding="utf-8") as f:
            json.dump(favs, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ---------- PRACTICE CANDIDATES / APPROVED PRACTICES ----------

def load_approved_practices():
    if not os.path.exists(APPROVED_PRACTICES_FILE):
        return {"mantra": [], "meditation": []}
    try:
        with open(APPROVED_PRACTICES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("mantra", [])
                data.setdefault("meditation", [])
                return data
            return {"mantra": [], "meditation": []}
    except json.JSONDecodeError:
        return {"mantra": [], "meditation": []}
    except Exception:
        return {"mantra": [], "meditation": []}


def save_approved_practices(data: dict):
    try:
        with open(APPROVED_PRACTICES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def load_practice_candidates():
    if not os.path.exists(PRACTICE_CANDIDATES_FILE):
        return []
    try:
        with open(PRACTICE_CANDIDATES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and isinstance(data.get("candidates"), list):
                return data["candidates"]
            return []
    except json.JSONDecodeError:
        return []
    except Exception:
        return []


def save_practice_candidates(candidates: list):
    try:
        with open(PRACTICE_CANDIDATES_FILE, "w", encoding="utf-8") as f:
            json.dump(candidates, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
