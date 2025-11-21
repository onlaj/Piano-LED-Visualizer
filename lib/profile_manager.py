import sqlite3
import threading
import os
from typing import List, Dict, Optional
from lib.log_setup import logger

class ProfileManager:
    """Manage user profiles and per-song highscores.

    Schema:
        profiles(id INTEGER PK, name TEXT UNIQUE)
        highscores(id INTEGER PK, profile_id INTEGER, song_name TEXT, high_score INTEGER, UNIQUE(profile_id, song_name))
    """

    def __init__(self, db_path: str = "profiles.db", songs_dir: str = "Songs"):
        # Resolve relative DB path into project 'data' directory so file is visible & persistent
        if not os.path.isabs(db_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            data_dir = os.path.join(project_root, 'data')
            try:
                os.makedirs(data_dir, exist_ok=True)
            except OSError:
                # Fallback: keep relative path if directory cannot be created
                data_dir = os.path.abspath(project_root)
            db_path = os.path.join(data_dir, db_path)
        self.db_path = db_path
        self.songs_dir = songs_dir
        self._lock = threading.Lock()
        self._init_db()

    # --------------- Internal helpers ---------------
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
        except Exception:
            pass
        return conn

    def _init_db(self):
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS highscores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    song_name TEXT NOT NULL,
                    high_score INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(profile_id, song_name),
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    song_name TEXT NOT NULL,
                    loop INTEGER NOT NULL DEFAULT 1,
                    practice INTEGER NOT NULL DEFAULT 0,
                    tempo INTEGER NOT NULL DEFAULT 100,
                    hands INTEGER NOT NULL DEFAULT 0,
                    mute_hands INTEGER NOT NULL DEFAULT 0,
                    wrong_notes INTEGER NOT NULL DEFAULT 1,
                    future_notes INTEGER NOT NULL DEFAULT 0,
                    mistakes INTEGER NOT NULL DEFAULT 0,
                    start REAL NOT NULL DEFAULT 0,
                    end REAL NOT NULL DEFAULT 100,
                    lh_color INTEGER NOT NULL DEFAULT 5,
                    rh_color INTEGER NOT NULL DEFAULT 0,
                    prev_lh_color INTEGER NOT NULL DEFAULT 0,
                    prev_rh_color INTEGER NOT NULL DEFAULT 0,
                    lh_active INTEGER NOT NULL DEFAULT 1,
                    rh_active INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(profile_id, song_name),
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE       
                )
                """
            )
            conn.commit()

    def _list_song_files(self) -> List[str]:
        try:
            files = os.listdir(self.songs_dir)
        except FileNotFoundError:
            return []
        return [f for f in files if f.lower().endswith('.mid') and '_#' not in f]

    # --------------- Profile operations ---------------
    def create_profile(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Profile name cannot be empty")
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO profiles(name) VALUES(?)", (name,))
            conn.commit()
            cur.execute("SELECT id FROM profiles WHERE name=?", (name,))
            row = cur.fetchone()
            profile_id = row[0]
        # Ensure highscores rows exist
        self.ensure_song_entries(profile_id)
        return profile_id

    def get_profiles(self) -> List[Dict]:
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM profiles ORDER BY name COLLATE NOCASE ASC")
            rows = cur.fetchall()
        return [{"id": r[0], "name": r[1]} for r in rows]

    def get_profile_id(self, name: str) -> Optional[int]:
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM profiles WHERE name=?", (name,))
            row = cur.fetchone()
            return row[0] if row else None

    def get_or_create_profile(self, name: str) -> int:
        pid = self.get_profile_id(name)
        if pid is not None:
            return pid
        return self.create_profile(name)

    # --------------- Highscore and Learning segment operations ---------------
    def ensure_song_entries(self, profile_id: int):
        songs = self._list_song_files()
        if not songs:
            return
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            for song in songs:
                cur.execute(
                    "INSERT OR IGNORE INTO highscores(profile_id, song_name, high_score) VALUES(?,?,0)",
                    (profile_id, song)
                )
                cur.execute(
                    "INSERT OR IGNORE INTO learning_settings(profile_id, song_name, loop, tempo, hands, mute_hands, wrong_notes, future_notes, mistakes, start, end, lh_color, rh_color, prev_lh_color, prev_rh_color, lh_active, rh_active) VALUES(?,?,1,100,0,0,1,0,0,0,100,5,0,0,0,1,1)",
                    (profile_id, song)
                )
            conn.commit()

    def get_highscores(self, profile_id: int) -> Dict[str, int]:
        # Populate missing songs with 0
        self.ensure_song_entries(profile_id)
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT song_name, high_score FROM highscores WHERE profile_id=?", (profile_id,))
            rows = cur.fetchall()
        return {r[0]: r[1] for r in rows}

    def update_highscore(self, profile_id: int, song_name: str, new_score: int) -> bool:
        if new_score < 0:
            return False
        song_name = song_name.strip()
        if not song_name:
            return False
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            # Make sure row exists
            cur.execute(
                "INSERT OR IGNORE INTO highscores(profile_id, song_name, high_score) VALUES(?,?,0)",
                (profile_id, song_name)
            )
            # Only update if higher
            cur.execute(
                "UPDATE highscores SET high_score=? WHERE profile_id=? AND song_name=? AND high_score < ?",
                (new_score, profile_id, song_name, new_score)
            )
            changed = cur.rowcount > 0
            conn.commit()
        return changed

    def get_learning_settings(self, profile_id: int, song_name: str) -> Dict[str, int]:
        # Populate missing songs with 0
        self.ensure_song_entries(profile_id)
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT loop, practice, tempo, hands, mute_hands, wrong_notes, future_notes, mistakes, start, end, lh_color, rh_color, prev_lh_color, prev_rh_color, lh_active, rh_active FROM learning_settings WHERE profile_id=? AND song_name=?",
                (profile_id, song_name)
            )
        row = cur.fetchone()
        if row:
            ret_dict = {"loop": row[0], "practice": row[1], "tempo": row[2], "hands": row[3], "mute_hands": row[4], "wrong_notes": row[5], "future_notes": row[6], "mistakes": row[7], "start": row[8], "end": row[9], "lh_color": row[10], "rh_color": row[11], "prev_lh_color": row[12], "prev_rh_color": row[13], "lh_active": row[14], "rh_active": row[15]}
        else:
            logger.warning(f"No learning section found for profile {profile_id} and song {song_name}. Returning defaults.")
            ret_dict = {"loop": 1, "practice": 0, "tempo": 100, "hands": 0, "mute_hands": 0, "wrong_notes": 1, "future_notes": 0, "mistakes": 0, "start": 0, "end": 100, "lh_color": 5, "rh_color": 0, "prev_lh_color": 0, "prev_lh_color": 0, "lh_active": 1, "rh_active": 1}
        return ret_dict

    def update_learning_setting(self, profile_id: int, song_name: str, key: str, val: int) -> bool:
        song_name = song_name.strip()
        logger.info(f"Updating learning setting {key} for song {song_name} to {val}")
        if not song_name:
            return False
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            # Make sure row exists, we enter defaults first
            cur.execute(
                "INSERT OR IGNORE INTO learning_settings(profile_id, song_name, loop, tempo, hands, mute_hands, wrong_notes, future_notes, mistakes, start, end, lh_color, rh_color, prev_lh_color, prev_rh_color, lh_active, rh_active) VALUES(?,?,1,100,0,0,1,0,0,0,100,0,0,0,0,1,1)",
                (profile_id, song_name)
            )
            # Update
            cur.execute(
                "UPDATE learning_settings SET " + key + "=? WHERE profile_id=? AND song_name=?",
                (val, profile_id, song_name)
            )
            changed = cur.rowcount > 0
            conn.commit()
        return changed

    def delete_profile(self, profile_id: int):
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM profiles WHERE id=?", (profile_id,))
            conn.commit()
