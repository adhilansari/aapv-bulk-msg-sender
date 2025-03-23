import os
import json
import logging
import time
from datetime import datetime
import shutil

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages WhatsApp Web sessions and their persistence"""

    def __init__(self, base_dir="./assets/chrome_profile"):
        self.base_dir = os.path.abspath(base_dir)
        self.sessions_file = os.path.join(
            os.path.dirname(self.base_dir), "sessions.json"
        )
        self.sessions = self._load_sessions()

    def _load_sessions(self):
        """Load saved sessions from JSON file"""
        if os.path.exists(self.sessions_file):
            try:
                with open(self.sessions_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load sessions: {str(e)}")
                return {"sessions": [], "last_used": None}
        else:
            return {"sessions": [], "last_used": None}

    def _save_sessions(self):
        """Save sessions to JSON file"""
        try:
            with open(self.sessions_file, "w") as f:
                json.dump(self.sessions, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sessions: {str(e)}")

    def get_active_session(self):
        """Get the most recently used session"""
        if not self.sessions["sessions"]:
            return None

        if self.sessions["last_used"]:
            # Find the last used session
            for session in self.sessions["sessions"]:
                if session["id"] == self.sessions["last_used"]:
                    return session

        # If no last_used or it wasn't found, return the most recent one
        return sorted(
            self.sessions["sessions"],
            key=lambda x: x.get("last_active", 0),
            reverse=True,
        )[0]

    def create_session(self, name=None):
        """Create a new session"""
        timestamp = int(time.time())
        session_id = f"session_{timestamp}"

        if not name:
            name = f"Session {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')}"

        session = {
            "id": session_id,
            "name": name,
            "created": timestamp,
            "last_active": timestamp,
            "profile_path": os.path.join(self.base_dir, session_id),
        }

        # Create profile directory
        os.makedirs(session["profile_path"], exist_ok=True)

        # Add to sessions list
        self.sessions["sessions"].append(session)
        self.sessions["last_used"] = session_id
        self._save_sessions()

        return session

    def use_session(self, session_id):
        """Mark a session as being used"""
        for session in self.sessions["sessions"]:
            if session["id"] == session_id:
                session["last_active"] = int(time.time())
                self.sessions["last_used"] = session_id
                self._save_sessions()
                return session

        return None

    def delete_session(self, session_id):
        """Delete a session and its profile data"""
        for i, session in enumerate(self.sessions["sessions"]):
            if session["id"] == session_id:
                # Remove profile directory
                try:
                    if os.path.exists(session["profile_path"]):
                        shutil.rmtree(session["profile_path"])
                except Exception as e:
                    logger.error(f"Failed to delete profile directory: {str(e)}")

                # Remove from sessions list
                self.sessions["sessions"].pop(i)

                # Update last_used if needed
                if self.sessions["last_used"] == session_id:
                    self.sessions["last_used"] = None
                    if self.sessions["sessions"]:
                        self.sessions["last_used"] = self.sessions["sessions"][0]["id"]

                self._save_sessions()
                return True

        return False

    def list_sessions(self):
        """List all available sessions"""
        return self.sessions["sessions"]

    def cleanup_old_sessions(self, days=30):
        """Remove sessions older than specified days"""
        cutoff = int(time.time()) - (days * 86400)
        removed = 0

        for session_id in [s["id"] for s in self.sessions["sessions"]]:
            session = next(
                (s for s in self.sessions["sessions"] if s["id"] == session_id), None
            )
            if session and session.get("last_active", 0) < cutoff:
                if self.delete_session(session_id):
                    removed += 1

        return removed
