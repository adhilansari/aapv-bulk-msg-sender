import os
import json
import logging
import time
from datetime import datetime, timedelta
import threading
import uuid

logger = logging.getLogger(__name__)


class MessageScheduler:
    """Manages scheduled messages for future delivery"""

    def __init__(self, scheduler_dir="./data/scheduled"):
        self.scheduler_dir = os.path.abspath(scheduler_dir)
        self.schedule_file = os.path.join(self.scheduler_dir, "scheduled_messages.json")
        self.schedules = self._load_schedules()
        self._running = False
        self._scheduler_thread = None
        self._callbacks = {}

    def _load_schedules(self):
        """Load scheduled messages from JSON file"""
        os.makedirs(self.scheduler_dir, exist_ok=True)

        if os.path.exists(self.schedule_file):
            try:
                with open(self.schedule_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load schedules: {str(e)}")
                return {"schedules": []}
        else:
            return {"schedules": []}

    def _save_schedules(self):
        """Save scheduled messages to JSON file"""
        try:
            with open(self.schedule_file, "w", encoding="utf-8") as f:
                json.dump(self.schedules, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save schedules: {str(e)}")

    def get_all_schedules(self):
        """Get all scheduled messages"""
        return self.schedules["schedules"]

    def get_schedule(self, schedule_id):
        """Get a specific scheduled message by ID"""
        for schedule in self.schedules["schedules"]:
            if schedule["id"] == schedule_id:
                return schedule
        return None

    def add_schedule(
        self,
        name,
        contacts,
        message,
        attachments=None,
        scheduled_time=None,
        recurrence=None,
    ):
        """Add a new scheduled message"""
        if attachments is None:
            attachments = []

        # Generate a unique ID
        schedule_id = str(uuid.uuid4())

        # If no scheduled time is provided, default to 1 hour from now
        if scheduled_time is None:
            scheduled_time = (datetime.now() + timedelta(hours=1)).isoformat()
        elif isinstance(scheduled_time, datetime):
            scheduled_time = scheduled_time.isoformat()

        schedule = {
            "id": schedule_id,
            "name": name,
            "contacts": contacts,
            "message": message,
            "attachments": attachments,
            "scheduled_time": scheduled_time,
            "recurrence": recurrence,  # None, "daily", "weekly", "monthly"
            "created": datetime.now().isoformat(),
            "status": "pending",
            "last_run": None,
            "next_run": scheduled_time,
        }

        self.schedules["schedules"].append(schedule)
        self._save_schedules()
        return schedule

    def update_schedule(self, schedule_id, **kwargs):
        """Update an existing scheduled message"""
        for schedule in self.schedules["schedules"]:
            if schedule["id"] == schedule_id:
                # Update provided fields
                for key, value in kwargs.items():
                    if key in schedule:
                        schedule[key] = value

                # If scheduled_time was updated, update next_run as well
                if "scheduled_time" in kwargs:
                    schedule["next_run"] = kwargs["scheduled_time"]

                self._save_schedules()
                return schedule
        return None

    def delete_schedule(self, schedule_id):
        """Delete a scheduled message"""
        for i, schedule in enumerate(self.schedules["schedules"]):
            if schedule["id"] == schedule_id:
                deleted = self.schedules["schedules"].pop(i)
                self._save_schedules()
                return deleted
        return None

    def get_pending_schedules(self):
        """Get all pending scheduled messages"""
        now = datetime.now().isoformat()
        return [
            schedule
            for schedule in self.schedules["schedules"]
            if schedule["status"] == "pending" and schedule["next_run"] <= now
        ]

    def mark_as_completed(self, schedule_id, success=True):
        """Mark a scheduled message as completed"""
        for schedule in self.schedules["schedules"]:
            if schedule["id"] == schedule_id:
                schedule["last_run"] = datetime.now().isoformat()

                # Handle recurrence
                if schedule["recurrence"]:
                    next_run = None
                    last_run = datetime.fromisoformat(schedule["last_run"])

                    if schedule["recurrence"] == "daily":
                        next_run = (last_run + timedelta(days=1)).isoformat()
                    elif schedule["recurrence"] == "weekly":
                        next_run = (last_run + timedelta(weeks=1)).isoformat()
                    elif schedule["recurrence"] == "monthly":
                        # Approximate a month as 30 days
                        next_run = (last_run + timedelta(days=30)).isoformat()

                    if next_run:
                        schedule["next_run"] = next_run
                        schedule["status"] = "pending"
                    else:
                        schedule["status"] = "completed"
                else:
                    schedule["status"] = "completed"

                self._save_schedules()
                return schedule
        return None

    def register_callback(self, event_type, callback):
        """Register a callback function for scheduler events"""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    def _notify_callbacks(self, event_type, data):
        """Notify registered callbacks of an event"""
        if event_type in self._callbacks:
            for callback in self._callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in callback for {event_type}: {str(e)}")

    def start_scheduler(self, check_interval=60):
        """Start the scheduler thread to process scheduled messages"""
        if self._running:
            return False

        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, args=(check_interval,), daemon=True
        )
        self._scheduler_thread.start()
        logger.info("Message scheduler started")
        return True

    def stop_scheduler(self):
        """Stop the scheduler thread"""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=2)
            self._scheduler_thread = None
        logger.info("Message scheduler stopped")
        return True

    def _scheduler_loop(self, check_interval):
        """Main scheduler loop that checks for pending messages"""
        while self._running:
            try:
                # Check for pending schedules
                pending = self.get_pending_schedules()

                for schedule in pending:
                    logger.info(f"Processing scheduled message: {schedule['name']}")
                    self._notify_callbacks("schedule_ready", schedule)

                # Sleep for the check interval
                time.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(check_interval)  # Sleep even on error
