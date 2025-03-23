import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration settings"""

    def __init__(self, config_dir="./config"):
        self.config_dir = os.path.abspath(config_dir)
        self.config_file = os.path.join(self.config_dir, "settings.json")
        self.config = self._load_config()

    def _load_config(self):
        """Load configuration from JSON file"""
        os.makedirs(self.config_dir, exist_ok=True)

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load configuration: {str(e)}")
                return self._create_default_config()
        else:
            return self._create_default_config()

    def _create_default_config(self):
        """Create default configuration"""
        default_config = {
            "app": {
                "name": "WhatsApp Bulk Messenger Pro",
                "version": "1.1.0",
                "theme": "minty",
                "dark_mode": False,
                "window_size": "1200x900",
                "last_updated": datetime.now().isoformat(),
            },
            "messaging": {
                "default_country_code": "+91",
                "min_delay": 10,
                "max_delay": 20,
                "max_attachments": 10,
                "max_message_length": 40000,
                "auto_retry": True,
                "max_retries": 3,
            },
            "session": {
                "auto_refresh": True,
                "session_timeout": 3600,  # 1 hour
                "cleanup_days": 30,
            },
            "paths": {
                "logs_dir": "./logs",
                "data_dir": "./data",
                "templates_dir": "./data/templates",
                "chrome_profile_dir": "./assets/chrome_profile",
            },
            "features": {
                "enable_templates": True,
                "enable_scheduling": True,
                "enable_reporting": True,
                "enable_console_logging": True,
            },
        }

        self._save_config(default_config)
        return default_config

    def _save_config(self, config=None):
        """Save configuration to JSON file"""
        if config is None:
            config = self.config

        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")

    def get(self, section, key=None, default=None):
        """Get configuration value"""
        try:
            if key is None:
                return self.config.get(section, default)
            return self.config.get(section, {}).get(key, default)
        except Exception as e:
            logger.error(f"Error getting config value [{section}.{key}]: {str(e)}")
            return default

    def set(self, section, key, value):
        """Set configuration value"""
        try:
            if section not in self.config:
                self.config[section] = {}

            self.config[section][key] = value
            self.config["app"]["last_updated"] = datetime.now().isoformat()
            self._save_config()
            return True
        except Exception as e:
            logger.error(f"Error setting config value [{section}.{key}]: {str(e)}")
            return False

    def update_section(self, section, values):
        """Update multiple values in a section"""
        try:
            if section not in self.config:
                self.config[section] = {}

            self.config[section].update(values)
            self.config["app"]["last_updated"] = datetime.now().isoformat()
            self._save_config()
            return True
        except Exception as e:
            logger.error(f"Error updating config section [{section}]: {str(e)}")
            return False

    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.config = self._create_default_config()
        return True

    def export_config(self, export_path=None):
        """Export configuration to a file"""
        if export_path is None:
            export_path = os.path.join(
                self.config_dir,
                f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )

        try:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return export_path
        except Exception as e:
            logger.error(f"Failed to export configuration: {str(e)}")
            return None

    def import_config(self, import_path):
        """Import configuration from a file"""
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                imported_config = json.load(f)

            # Validate the imported config has required sections
            required_sections = ["app", "messaging", "session", "paths", "features"]
            for section in required_sections:
                if section not in imported_config:
                    raise ValueError(f"Missing required section: {section}")

            self.config = imported_config
            self.config["app"]["last_updated"] = datetime.now().isoformat()
            self._save_config()
            return True
        except Exception as e:
            logger.error(f"Failed to import configuration: {str(e)}")
            return False
