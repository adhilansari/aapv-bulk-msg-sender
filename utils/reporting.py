import os
import json
import csv
import logging
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from io import BytesIO
import base64

logger = logging.getLogger(__name__)


class MessageReporting:
    """Generates reports and analytics for message sending activities"""

    def __init__(self, reports_dir="./data/reports"):
        self.reports_dir = os.path.abspath(reports_dir)
        self.activity_file = os.path.join(self.reports_dir, "message_activity.json")
        self.activities = self._load_activities()

    def _load_activities(self):
        """Load message activities from JSON file"""
        os.makedirs(self.reports_dir, exist_ok=True)

        if os.path.exists(self.activity_file):
            try:
                with open(self.activity_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load activities: {str(e)}")
                return {"activities": []}
        else:
            return {"activities": []}

    def _save_activities(self):
        """Save message activities to JSON file"""
        try:
            with open(self.activity_file, "w", encoding="utf-8") as f:
                json.dump(self.activities, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save activities: {str(e)}")

    def log_activity(
        self,
        phone,
        message,
        attachments=None,
        status="success",
        error=None,
        batch_id=None,
    ):
        """Log a message sending activity"""
        if attachments is None:
            attachments = []

        activity = {
            "timestamp": datetime.now().isoformat(),
            "phone": phone,
            "message_length": len(message) if message else 0,
            "has_attachments": bool(attachments),
            "attachment_count": len(attachments),
            "status": status,
            "error": error,
            "batch_id": batch_id,
        }

        self.activities["activities"].append(activity)
        self._save_activities()
        return activity

    def log_batch_start(self, contact_count, batch_name=None):
        """Log the start of a batch sending operation"""
        batch_id = f"batch_{int(datetime.now().timestamp())}"

        batch_info = {
            "batch_id": batch_id,
            "name": batch_name or f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "contact_count": contact_count,
            "success_count": 0,
            "failure_count": 0,
            "status": "in_progress",
        }

        if "batches" not in self.activities:
            self.activities["batches"] = []

        self.activities["batches"].append(batch_info)
        self._save_activities()
        return batch_id

    def log_batch_end(self, batch_id, success_count, failure_count):
        """Log the end of a batch sending operation"""
        if "batches" not in self.activities:
            return None

        for batch in self.activities["batches"]:
            if batch["batch_id"] == batch_id:
                batch["end_time"] = datetime.now().isoformat()
                batch["success_count"] = success_count
                batch["failure_count"] = failure_count
                batch["status"] = "completed"
                self._save_activities()
                return batch

        return None

    def get_activities(self, days=7, status=None, batch_id=None):
        """Get message activities filtered by criteria"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        filtered = [
            activity
            for activity in self.activities["activities"]
            if activity["timestamp"] >= cutoff
            and (status is None or activity["status"] == status)
            and (batch_id is None or activity["batch_id"] == batch_id)
        ]

        return filtered

    def get_batches(self, days=30, status=None):
        """Get batch operations filtered by criteria"""
        if "batches" not in self.activities:
            return []

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        filtered = [
            batch
            for batch in self.activities["batches"]
            if batch["start_time"] >= cutoff
            and (status is None or batch["status"] == status)
        ]

        return filtered

    def generate_daily_report(self, days=7):
        """Generate a daily activity report"""
        activities = self.get_activities(days=days)

        if not activities:
            return {
                "period": f"Last {days} days",
                "total_messages": 0,
                "success_rate": 0,
                "daily_counts": [],
            }

        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(activities)
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        # Daily counts
        daily_counts = df.groupby("date").size().reset_index()
        daily_counts.columns = ["date", "count"]

        # Success rate
        success_count = df[df["status"] == "success"].shape[0]
        total_count = df.shape[0]
        success_rate = (success_count / total_count) * 100 if total_count > 0 else 0

        report = {
            "period": f"Last {days} days",
            "total_messages": total_count,
            "success_count": success_count,
            "failure_count": total_count - success_count,
            "success_rate": round(success_rate, 2),
            "daily_counts": daily_counts.to_dict(orient="records"),
        }

        return report

    def export_to_csv(self, filepath=None, days=30):
        """Export activities to CSV file"""
        if filepath is None:
            filepath = os.path.join(
                self.reports_dir,
                f"message_activity_{datetime.now().strftime('%Y%m%d')}.csv",
            )

        activities = self.get_activities(days=days)

        if not activities:
            return None

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "timestamp",
                        "phone",
                        "message_length",
                        "has_attachments",
                        "attachment_count",
                        "status",
                        "error",
                        "batch_id",
                    ],
                )
                writer.writeheader()
                writer.writerows(activities)

            return filepath
        except Exception as e:
            logger.error(f"Failed to export to CSV: {str(e)}")
            return None

    def generate_chart(self, chart_type="daily", days=7):
        """Generate a chart visualization of message activity"""
        activities = self.get_activities(days=days)

        if not activities:
            return None

        df = pd.DataFrame(activities)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date

        plt.figure(figsize=(10, 6))

        if chart_type == "daily":
            # Daily message count
            daily_counts = df.groupby("date").size()
            daily_counts.plot(kind="bar", color="skyblue")
            plt.title(f"Daily Message Count (Last {days} Days)")
            plt.xlabel("Date")
            plt.ylabel("Number of Messages")
            plt.xticks(rotation=45)
            plt.tight_layout()

        elif chart_type == "status":
            # Status distribution
            status_counts = df["status"].value_counts()
            status_counts.plot(kind="pie", autopct="%1.1f%%")
            plt.title("Message Status Distribution")
            plt.ylabel("")
            plt.tight_layout()

        elif chart_type == "hourly":
            # Hourly distribution
            df["hour"] = df["timestamp"].dt.hour
            hourly_counts = df.groupby("hour").size()
            hourly_counts.plot(kind="line", marker="o")
            plt.title("Hourly Message Distribution")
            plt.xlabel("Hour of Day")
            plt.ylabel("Number of Messages")
            plt.xticks(range(24))
            plt.grid(True, linestyle="--", alpha=0.7)
            plt.tight_layout()

        # Save chart to BytesIO
        buffer = BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)

        # Convert to base64 for embedding in HTML
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close()

        return f"data:image/png;base64,{image_base64}"

    def get_summary_stats(self, days=30):
        """Get summary statistics for message activities"""
        activities = self.get_activities(days=days)

        if not activities:
            return {
                "total_messages": 0,
                "success_rate": 0,
                "with_attachments": 0,
                "avg_message_length": 0,
            }

        df = pd.DataFrame(activities)

        total = len(activities)
        success = sum(1 for a in activities if a["status"] == "success")
        with_attachments = sum(1 for a in activities if a["has_attachments"])

        avg_length = (
            sum(a["message_length"] for a in activities) / total if total > 0 else 0
        )

        return {
            "total_messages": total,
            "success_count": success,
            "failure_count": total - success,
            "success_rate": round((success / total) * 100, 2) if total > 0 else 0,
            "with_attachments": with_attachments,
            "with_attachments_pct": (
                round((with_attachments / total) * 100, 2) if total > 0 else 0
            ),
            "avg_message_length": round(avg_length, 2),
        }
