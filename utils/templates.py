import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageTemplates:
    """Manages message templates for reuse"""

    def __init__(self, templates_dir="./data/templates"):
        self.templates_dir = os.path.abspath(templates_dir)
        self.templates_file = os.path.join(self.templates_dir, "message_templates.json")
        self.templates = self._load_templates()

    def _load_templates(self):
        """Load templates from JSON file"""
        os.makedirs(os.path.dirname(self.templates_file), exist_ok=True)

        if os.path.exists(self.templates_file):
            try:
                with open(self.templates_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load templates: {str(e)}")
                return {"templates": []}
        else:
            # Create default templates if file doesn't exist
            default_templates = {
                "templates": [
                    {
                        "id": "welcome",
                        "name": "Welcome Message",
                        "content": "Hello {{name}},\n\nThank you for connecting with us. We're excited to have you on board!\n\nBest regards,\n{{sender}}",
                        "created": datetime.now().isoformat(),
                        "last_used": None,
                    },
                    {
                        "id": "follow_up",
                        "name": "Follow-up Message",
                        "content": "Hi {{name}},\n\nI wanted to follow up on our previous conversation. Let me know if you have any questions.\n\nRegards,\n{{sender}}",
                        "created": datetime.now().isoformat(),
                        "last_used": None,
                    },
                ]
            }
            self._save_templates(default_templates)
            return default_templates

    def _save_templates(self, templates=None):
        """Save templates to JSON file"""
        if templates is None:
            templates = self.templates

        try:
            with open(self.templates_file, "w", encoding="utf-8") as f:
                json.dump(templates, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save templates: {str(e)}")

    def get_all_templates(self):
        """Get all available templates"""
        return self.templates["templates"]

    def get_template(self, template_id):
        """Get a specific template by ID"""
        for template in self.templates["templates"]:
            if template["id"] == template_id:
                return template
        return None

    def add_template(self, name, content):
        """Add a new template"""
        template_id = name.lower().replace(" ", "_")

        # Check if template with this ID already exists
        existing = self.get_template(template_id)
        if existing:
            # Generate a unique ID by appending a timestamp
            template_id = f"{template_id}_{int(datetime.now().timestamp())}"

        template = {
            "id": template_id,
            "name": name,
            "content": content,
            "created": datetime.now().isoformat(),
            "last_used": None,
        }

        self.templates["templates"].append(template)
        self._save_templates()
        return template

    def update_template(self, template_id, name=None, content=None):
        """Update an existing template"""
        for template in self.templates["templates"]:
            if template["id"] == template_id:
                if name:
                    template["name"] = name
                if content:
                    template["content"] = content
                self._save_templates()
                return template
        return None

    def delete_template(self, template_id):
        """Delete a template"""
        for i, template in enumerate(self.templates["templates"]):
            if template["id"] == template_id:
                deleted = self.templates["templates"].pop(i)
                self._save_templates()
                return deleted
        return None

    def mark_as_used(self, template_id):
        """Mark a template as used"""
        for template in self.templates["templates"]:
            if template["id"] == template_id:
                template["last_used"] = datetime.now().isoformat()
                self._save_templates()
                return template
        return None

    def render_template(self, template_id, variables=None):
        """Render a template with variables"""
        if variables is None:
            variables = {}

        template = self.get_template(template_id)
        if not template:
            return None

        content = template["content"]

        # Replace variables in the template
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            content = content.replace(placeholder, str(value))

        # Mark template as used
        self.mark_as_used(template_id)

        return content
