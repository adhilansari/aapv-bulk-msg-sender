import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import winsound
from ttkbootstrap import Style
import pandas as pd
import threading
import random
import time
from selenium.webdriver.common.by import By
import os
import sys
from datetime import datetime, timedelta
from core.client import WhatsAppClient
from core.session_manager import SessionManager
from utils.validator import (
    validate_phone_numbers,
    validate_message,
    validate_attachments,
)
from utils.logger import setup_logging, get_logger
from utils.templates import MessageTemplates
from utils.config import ConfigManager
from utils.scheduler import MessageScheduler
from utils.reporting import MessageReporting


class BulkSenderApp:
    def __init__(self):
        # Initialize utilities
        self.logger = setup_logging(enable_console=True)
        self.config = ConfigManager()
        self.session_manager = SessionManager(
            self.config.get("paths", "chrome_profile_dir")
        )
        self.templates = MessageTemplates(self.config.get("paths", "templates_dir"))
        self.scheduler = MessageScheduler()
        self.reporting = MessageReporting()

        # Start the scheduler if enabled
        if self.config.get("features", "enable_scheduling"):
            self.scheduler.register_callback(
                "schedule_ready", self._handle_scheduled_message
            )
            self.scheduler.start_scheduler()

        # Initialize UI
        theme = self.config.get("app", "theme")
        self.root = Style(theme=theme).master
        self.root.title(self.config.get("app", "name"))
        self.root.geometry(self.config.get("app", "window_size"))

    def _handle_scheduled_message(self, schedule_data):
        """Handle a scheduled message that's ready to be sent"""
        try:
            client = WhatsAppClient()
            self.logger.info(f"Processing scheduled message: {schedule_data['name']}")

            # Validate required fields
            required_fields = ["phone", "message", "scheduled_time"]
            if not all(field in schedule_data for field in required_fields):
                raise ValueError("Invalid schedule data - missing required fields")

            # Send message with attachments
            result = client.send_message(
                phone=schedule_data["phone"],
                message=schedule_data["message"],
                attachments=schedule_data.get("attachments", []),
            )

            # Update reporting
            status = "success" if result else "failed"
            self.reporting.log_message(
                phone=schedule_data["phone"],
                message=schedule_data["message"],
                status=status,
                attachments=schedule_data.get("attachments", []),
                scheduled_time=schedule_data["scheduled_time"],
            )

            # Update scheduler status
            self.scheduler.update_schedule_status(
                schedule_data["id"], status="completed" if result else "failed"
            )

        except Exception as e:
            self.logger.error(f"Failed to process scheduled message: {str(e)}")
            self.scheduler.update_schedule_status(schedule_data["id"], "error")
            if "client" in locals():
                client._capture_screenshot(f"scheduled_error_{schedule_data['id']}")

        # Initialize state variables
        self.attachments = []
        self._should_stop = False
        self.current_session = None

        # Setup UI and check session
        self._setup_ui()
        self._check_session()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Log application start
        get_logger(__name__).info("Application started")

    def _setup_ui(self):
        """Initialize user interface components"""
        # Create notebook for tabbed interface
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create main tabs
        self.tab_send = ttk.Frame(self.notebook)
        self.tab_templates = ttk.Frame(self.notebook)
        self.tab_scheduled = ttk.Frame(self.notebook)
        self.tab_reports = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)

        # Add tabs to notebook
        self.notebook.add(self.tab_send, text="Send Messages")

        if self.config.get("features", "enable_templates"):
            self.notebook.add(self.tab_templates, text="Templates")

        if self.config.get("features", "enable_scheduling"):
            self.notebook.add(self.tab_scheduled, text="Scheduled")

        if self.config.get("features", "enable_reporting"):
            self.notebook.add(self.tab_reports, text="Reports")

        self.notebook.add(self.tab_settings, text="Settings")

        # Setup each tab
        self._setup_send_tab()

        if self.config.get("features", "enable_templates"):
            self._setup_templates_tab()

        if self.config.get("features", "enable_scheduling"):
            self._setup_scheduled_tab()

        if self.config.get("features", "enable_reporting"):
            self._setup_reports_tab()

        self._setup_settings_tab()

    def _setup_send_tab(self):
        """Setup the main message sending tab"""
        main_frame = ttk.Frame(self.tab_send, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Session status panel
        self._create_session_panel(main_frame)

        # File selection section
        self._create_file_section(main_frame)

        # Preview table
        self._create_preview_table(main_frame)

        # Message composition area
        self._create_message_section(main_frame)

        # Progress tracking
        self._create_progress_section(main_frame)

        # Control buttons
        self._create_control_buttons(main_frame)

    def _setup_templates_tab(self):
        """Setup the message templates tab"""
        templates_frame = ttk.Frame(self.tab_templates, padding=10)
        templates_frame.pack(fill=tk.BOTH, expand=True)

        # Templates list
        list_frame = ttk.LabelFrame(templates_frame, text="Available Templates")
        list_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 5))

        # Template list with scrollbar
        self.template_listbox = tk.Listbox(list_frame, width=30)
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.template_listbox.yview
        )
        self.template_listbox.configure(yscrollcommand=scrollbar.set)
        self.template_listbox.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        # Bind selection event
        self.template_listbox.bind("<<ListboxSelect>>", self._on_template_select)

        # Template buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="New Template", command=self._new_template).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="Delete", command=self._delete_template).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="Use Template", command=self._use_template).pack(
            side=tk.RIGHT, padx=2
        )

        # Template editor
        editor_frame = ttk.LabelFrame(templates_frame, text="Template Editor")
        editor_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT, padx=(5, 0))

        # Template name
        name_frame = ttk.Frame(editor_frame)
        name_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(name_frame, text="Template Name:").pack(side=tk.LEFT)
        self.template_name = ttk.Entry(name_frame, width=30)
        self.template_name.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Template content
        ttk.Label(editor_frame, text="Template Content:").pack(anchor=tk.W, padx=5)
        self.template_content = tk.Text(editor_frame, height=15, wrap=tk.WORD)
        self.template_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Variables help
        variables_frame = ttk.LabelFrame(editor_frame, text="Available Variables")
        variables_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(
            variables_frame,
            text="Use {{name}} for recipient's name, {{sender}} for your name",
        ).pack(padx=5, pady=5)

        # Save button
        ttk.Button(
            editor_frame, text="Save Template", command=self._save_template
        ).pack(pady=10)

        # Load templates
        self._load_templates()

    def _setup_scheduled_tab(self):
        """Setup the scheduled messages tab"""
        scheduled_frame = ttk.Frame(self.tab_scheduled, padding=10)
        scheduled_frame.pack(fill=tk.BOTH, expand=True)

        # Scheduled messages list
        list_frame = ttk.LabelFrame(scheduled_frame, text="Scheduled Messages")
        list_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 5))

        # Create treeview for scheduled messages
        columns = ("name", "status", "scheduled_time", "contacts")
        self.scheduled_tree = ttk.Treeview(list_frame, columns=columns, show="headings")

        # Define headings
        self.scheduled_tree.heading("name", text="Name")
        self.scheduled_tree.heading("status", text="Status")
        self.scheduled_tree.heading("scheduled_time", text="Scheduled Time")
        self.scheduled_tree.heading("contacts", text="Contacts")

        # Define columns
        self.scheduled_tree.column("name", width=150)
        self.scheduled_tree.column("status", width=80)
        self.scheduled_tree.column("scheduled_time", width=150)
        self.scheduled_tree.column("contacts", width=80)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.scheduled_tree.yview
        )
        self.scheduled_tree.configure(yscrollcommand=scrollbar.set)
        self.scheduled_tree.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        # Bind selection event
        self.scheduled_tree.bind("<<TreeviewSelect>>", self._on_schedule_select)

        # Buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="New Schedule", command=self._new_schedule).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="Delete", command=self._delete_schedule).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_schedules).pack(
            side=tk.RIGHT, padx=2
        )

        # Schedule details
        details_frame = ttk.LabelFrame(scheduled_frame, text="Schedule Details")
        details_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT, padx=(5, 0))

        # Schedule name
        name_frame = ttk.Frame(details_frame)
        name_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(name_frame, text="Name:").pack(side=tk.LEFT)
        self.schedule_name = ttk.Entry(name_frame, width=30)
        self.schedule_name.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Schedule time
        time_frame = ttk.Frame(details_frame)
        time_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(time_frame, text="Date & Time:").pack(side=tk.LEFT)
        self.schedule_date = ttk.Entry(time_frame, width=15)
        self.schedule_date.pack(side=tk.LEFT, padx=5)
        ttk.Button(time_frame, text="Set Date", command=self._set_schedule_date).pack(
            side=tk.LEFT
        )

        # Recurrence
        recur_frame = ttk.Frame(details_frame)
        recur_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(recur_frame, text="Recurrence:").pack(side=tk.LEFT)
        self.schedule_recurrence = ttk.Combobox(
            recur_frame, values=["None", "Daily", "Weekly", "Monthly"]
        )
        self.schedule_recurrence.current(0)
        self.schedule_recurrence.pack(side=tk.LEFT, padx=5)

        # Contacts file
        contacts_frame = ttk.Frame(details_frame)
        contacts_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(contacts_frame, text="Contacts File:").pack(side=tk.LEFT)
        self.schedule_contacts = ttk.Entry(contacts_frame, width=30)
        self.schedule_contacts.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(
            contacts_frame, text="Browse", command=self._browse_schedule_contacts
        ).pack(side=tk.RIGHT)

        # Message
        ttk.Label(details_frame, text="Message:").pack(anchor=tk.W, padx=5)
        self.schedule_message = tk.Text(details_frame, height=10, wrap=tk.WORD)
        self.schedule_message.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Attachments
        attach_frame = ttk.Frame(details_frame)
        attach_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(
            attach_frame, text="Add Attachments", command=self._add_schedule_attachments
        ).pack(side=tk.LEFT)
        self.schedule_attachments_label = ttk.Label(attach_frame, text="No attachments")
        self.schedule_attachments_label.pack(side=tk.LEFT, padx=5)
        self.schedule_attachments = []

        # Save button
        ttk.Button(
            details_frame, text="Save Schedule", command=self._save_schedule
        ).pack(pady=10)

        # Load schedules
        self._refresh_schedules()

    def _setup_reports_tab(self):
        """Setup the reports and analytics tab"""
        reports_frame = ttk.Frame(self.tab_reports, padding=10)
        reports_frame.pack(fill=tk.BOTH, expand=True)

        # Controls frame
        controls_frame = ttk.Frame(reports_frame)
        controls_frame.pack(fill=tk.X, pady=5)

        # Time period selection
        ttk.Label(controls_frame, text="Time Period:").pack(side=tk.LEFT)
        self.report_period = ttk.Combobox(
            controls_frame, values=["Last 7 days", "Last 30 days", "Last 90 days"]
        )
        self.report_period.current(0)
        self.report_period.pack(side=tk.LEFT, padx=5)

        # Chart type selection
        ttk.Label(controls_frame, text="Chart Type:").pack(side=tk.LEFT, padx=(10, 0))
        self.chart_type = ttk.Combobox(
            controls_frame, values=["Daily", "Status", "Hourly"]
        )
        self.chart_type.current(0)
        self.chart_type.pack(side=tk.LEFT, padx=5)

        # Generate button
        ttk.Button(
            controls_frame, text="Generate Report", command=self._generate_report
        ).pack(side=tk.LEFT, padx=10)

        # Export button
        ttk.Button(
            controls_frame, text="Export to CSV", command=self._export_report
        ).pack(side=tk.RIGHT)

        # Summary stats frame
        stats_frame = ttk.LabelFrame(reports_frame, text="Summary Statistics")
        stats_frame.pack(fill=tk.X, pady=10)

        # Stats grid
        self.stats_labels = {}
        stats_grid = [
            ("Total Messages:", "total_messages"),
            ("Success Rate:", "success_rate"),
            ("Successful:", "success_count"),
            ("Failed:", "failure_count"),
            ("With Attachments:", "with_attachments"),
            ("Avg Message Length:", "avg_message_length"),
        ]

        for i, (label_text, key) in enumerate(stats_grid):
            row, col = divmod(i, 3)
            ttk.Label(stats_frame, text=label_text).grid(
                row=row, column=col * 2, padx=5, pady=5, sticky=tk.W
            )
            self.stats_labels[key] = ttk.Label(stats_frame, text="0")
            self.stats_labels[key].grid(
                row=row, column=col * 2 + 1, padx=5, pady=5, sticky=tk.W
            )

        # Chart frame
        chart_frame = ttk.LabelFrame(reports_frame, text="Activity Chart")
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Chart display (using Label to show image)
        self.chart_label = ttk.Label(chart_frame)
        self.chart_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Recent activity frame
        activity_frame = ttk.LabelFrame(reports_frame, text="Recent Activity")
        activity_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Activity table
        columns = ("timestamp", "phone", "status", "message_length", "attachments")
        self.activity_tree = ttk.Treeview(
            activity_frame, columns=columns, show="headings"
        )

        # Define headings
        self.activity_tree.heading("timestamp", text="Time")
        self.activity_tree.heading("phone", text="Phone")
        self.activity_tree.heading("status", text="Status")
        self.activity_tree.heading("message_length", text="Length")
        self.activity_tree.heading("attachments", text="Attachments")

        # Define columns
        self.activity_tree.column("timestamp", width=150)
        self.activity_tree.column("phone", width=120)
        self.activity_tree.column("status", width=80)
        self.activity_tree.column("message_length", width=80)
        self.activity_tree.column("attachments", width=80)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(
            activity_frame, orient="vertical", command=self.activity_tree.yview
        )
        self.activity_tree.configure(yscrollcommand=scrollbar.set)
        self.activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial report
        self._generate_report()

    def _setup_settings_tab(self):
        """Setup the settings tab"""
        settings_frame = ttk.Frame(self.tab_settings, padding=10)
        settings_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for settings categories
        settings_notebook = ttk.Notebook(settings_frame)
        settings_notebook.pack(fill=tk.BOTH, expand=True)

        # Create settings tabs
        general_tab = ttk.Frame(settings_notebook)
        messaging_tab = ttk.Frame(settings_notebook)
        appearance_tab = ttk.Frame(settings_notebook)
        advanced_tab = ttk.Frame(settings_notebook)

        settings_notebook.add(general_tab, text="General")
        settings_notebook.add(messaging_tab, text="Messaging")
        settings_notebook.add(appearance_tab, text="Appearance")
        settings_notebook.add(advanced_tab, text="Advanced")

        # General settings
        self._create_general_settings(general_tab)

        # Messaging settings
        self._create_messaging_settings(messaging_tab)

        # Appearance settings
        self._create_appearance_settings(appearance_tab)

        # Advanced settings
        self._create_advanced_settings(advanced_tab)

        # Action buttons
        btn_frame = ttk.Frame(settings_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text="Save Settings", command=self._save_settings).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(
            btn_frame, text="Reset to Defaults", command=self._reset_settings
        ).pack(side=tk.RIGHT, padx=5)

    def _create_general_settings(self, parent):
        """Create general settings controls"""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Application name
        name_frame = ttk.Frame(frame)
        name_frame.pack(fill=tk.X, pady=5)
        ttk.Label(name_frame, text="Application Name:").pack(side=tk.LEFT)
        self.setting_app_name = ttk.Entry(name_frame, width=30)
        self.setting_app_name.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.setting_app_name.insert(0, self.config.get("app", "name"))

        # Window size
        size_frame = ttk.Frame(frame)
        size_frame.pack(fill=tk.X, pady=5)
        ttk.Label(size_frame, text="Window Size:").pack(side=tk.LEFT)
        self.setting_window_size = ttk.Entry(size_frame, width=15)
        self.setting_window_size.pack(side=tk.LEFT, padx=5)
        self.setting_window_size.insert(0, self.config.get("app", "window_size"))

        # Feature toggles
        toggle_frame = ttk.LabelFrame(frame, text="Features")
        toggle_frame.pack(fill=tk.X, pady=10)

        # Templates toggle
        self.setting_enable_templates = tk.BooleanVar(
            value=self.config.get("features", "enable_templates")
        )
        ttk.Checkbutton(
            toggle_frame,
            text="Enable Templates",
            variable=self.setting_enable_templates,
        ).pack(anchor=tk.W, padx=5, pady=2)

        # Scheduling toggle
        self.setting_enable_scheduling = tk.BooleanVar(
            value=self.config.get("features", "enable_scheduling")
        )
        ttk.Checkbutton(
            toggle_frame,
            text="Enable Scheduling",
            variable=self.setting_enable_scheduling,
        ).pack(anchor=tk.W, padx=5, pady=2)

        # Reporting toggle
        self.setting_enable_reporting = tk.BooleanVar(
            value=self.config.get("features", "enable_reporting")
        )
        ttk.Checkbutton(
            toggle_frame,
            text="Enable Reporting",
            variable=self.setting_enable_reporting,
        ).pack(anchor=tk.W, padx=5, pady=2)

        # Console logging toggle
        self.setting_enable_console = tk.BooleanVar(
            value=self.config.get("features", "enable_console_logging")
        )
        ttk.Checkbutton(
            toggle_frame,
            text="Enable Console Logging",
            variable=self.setting_enable_console,
        ).pack(anchor=tk.W, padx=5, pady=2)

    def _create_messaging_settings(self, parent):
        """Create messaging settings controls"""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Default country code
        country_frame = ttk.Frame(frame)
        country_frame.pack(fill=tk.X, pady=5)
        ttk.Label(country_frame, text="Default Country Code:").pack(side=tk.LEFT)
        self.setting_country_code = ttk.Entry(country_frame, width=10)
        self.setting_country_code.pack(side=tk.LEFT, padx=5)
        self.setting_country_code.insert(
            0, self.config.get("messaging", "default_country_code")
        )

        # Delay settings
        delay_frame = ttk.LabelFrame(frame, text="Message Delay (seconds)")
        delay_frame.pack(fill=tk.X, pady=10)

        min_frame = ttk.Frame(delay_frame)
        min_frame.pack(fill=tk.X, pady=5)
        ttk.Label(min_frame, text="Minimum Delay:").pack(side=tk.LEFT)
        self.setting_min_delay = ttk.Entry(min_frame, width=10)
        self.setting_min_delay.pack(side=tk.LEFT, padx=5)
        self.setting_min_delay.insert(0, str(self.config.get("messaging", "min_delay")))

        max_frame = ttk.Frame(delay_frame)
        max_frame.pack(fill=tk.X, pady=5)
        ttk.Label(max_frame, text="Maximum Delay:").pack(side=tk.LEFT)
        self.setting_max_delay = ttk.Entry(max_frame, width=10)
        self.setting_max_delay.pack(side=tk.LEFT, padx=5)
        self.setting_max_delay.insert(0, str(self.config.get("messaging", "max_delay")))

        # Limits
        limits_frame = ttk.LabelFrame(frame, text="Limits")
        limits_frame.pack(fill=tk.X, pady=10)

        attach_frame = ttk.Frame(limits_frame)
        attach_frame.pack(fill=tk.X, pady=5)
        ttk.Label(attach_frame, text="Max Attachments:").pack(side=tk.LEFT)
        self.setting_max_attachments = ttk.Entry(attach_frame, width=10)
        self.setting_max_attachments.pack(side=tk.LEFT, padx=5)
        self.setting_max_attachments.insert(
            0, str(self.config.get("messaging", "max_attachments"))
        )

        msg_frame = ttk.Frame(limits_frame)
        msg_frame.pack(fill=tk.X, pady=5)
        ttk.Label(msg_frame, text="Max Message Length:").pack(side=tk.LEFT)
        self.setting_max_length = ttk.Entry(msg_frame, width=10)
        self.setting_max_length.pack(side=tk.LEFT, padx=5)
        self.setting_max_length.insert(
            0, str(self.config.get("messaging", "max_message_length"))
        )

        # Auto retry
        retry_frame = ttk.Frame(frame)
        retry_frame.pack(fill=tk.X, pady=5)
        self.setting_auto_retry = tk.BooleanVar(
            value=self.config.get("messaging", "auto_retry")
        )
        ttk.Checkbutton(
            retry_frame,
            text="Auto Retry Failed Messages",
            variable=self.setting_auto_retry,
        ).pack(side=tk.LEFT)

        ttk.Label(retry_frame, text="Max Retries:").pack(side=tk.LEFT, padx=(10, 0))
        self.setting_max_retries = ttk.Entry(retry_frame, width=5)
        self.setting_max_retries.pack(side=tk.LEFT, padx=5)
        self.setting_max_retries.insert(
            0, str(self.config.get("messaging", "max_retries"))
        )

    def _pick_color(self, color_type):
        """Handle color selection dialog"""
        color = filedialog.askcolor(title=f"Select {color_type.capitalize()} Color")[1]
        if color:
            self.config.set("appearance", f"{color_type}_color", color)
            self._update_color_preview()

    def _update_color_preview(self):
        """Update color preview box with current colors"""
        primary = self.config.get("appearance", "primary_color", fallback="#ffffff")
        secondary = self.config.get("appearance", "secondary_color", fallback="#ffffff")
        self.color_preview.config(background=primary)
        self.color_preview.config(foreground=secondary)

    def _create_appearance_settings(self, parent):
        """Create appearance settings controls"""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Theme Selection
        theme_frame = ttk.LabelFrame(frame, text="Interface Theme")
        theme_frame.pack(fill=tk.X, pady=5)

        ttk.Label(theme_frame, text="Select Theme:").pack(side=tk.LEFT, padx=5)
        # Initialize color preview before creating the widget
        self.color_preview = ttk.Frame(theme_frame, width=50, height=24)
        self.color_preview.pack(side=tk.RIGHT, padx=5)
        self._update_color_preview()
        self.theme_selector = ttk.Combobox(
            theme_frame, values=Style().theme_names(), state="readonly"
        )
        self.theme_selector.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.theme_selector.set(
            self.config.get("appearance", "theme", fallback="litera")
        )

        # Font Settings
        font_frame = ttk.LabelFrame(frame, text="Font Settings")
        font_frame.pack(fill=tk.X, pady=5)

        ttk.Label(font_frame, text="Font Family:").pack(side=tk.LEFT, padx=5)
        self.font_family = ttk.Combobox(
            font_frame, values=[""] + list(tk.font.families()), state="readonly"
        )
        self.font_family.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.font_family.set(
            self.config.get("appearance", "font_family", fallback="Segoe UI")
        )

        ttk.Label(font_frame, text="Size:").pack(side=tk.LEFT, padx=(10, 5))
        self.font_size = ttk.Spinbox(font_frame, from_=8, to=18, width=5)
        self.font_size.pack(side=tk.LEFT)
        self.font_size.set(self.config.get("appearance", "font_size", fallback=10))

        # Color Customization
        color_frame = ttk.LabelFrame(frame, text="Color Customization")
        color_frame.pack(fill=tk.X, pady=5)

        ttk.Button(
            color_frame,
            text="Primary Color",
            command=lambda: self._pick_color("primary"),
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            color_frame,
            text="Secondary Color",
            command=lambda: self._pick_color("secondary"),
        ).pack(side=tk.LEFT, padx=5)

        self.color_preview = ttk.Frame(color_frame, width=50, height=24)
        self.color_preview.pack(side=tk.RIGHT, padx=5)
        self._update_color_preview()

        # UI Density
        density_frame = ttk.Frame(frame)
        density_frame.pack(fill=tk.X, pady=5)

        ttk.Label(density_frame, text="UI Density:").pack(side=tk.LEFT, padx=5)
        self.ui_density = ttk.Combobox(
            density_frame, values=["Compact", "Normal", "Spacious"], state="readonly"
        )
        self.ui_density.pack(side=tk.LEFT, padx=5)
        self.ui_density.set(self.config.get("appearance", "density", fallback="Normal"))

    def _create_file_section(self, parent):
        """File selection components"""
        file_frame = ttk.LabelFrame(parent, text="1. Select Contacts File")
        file_frame.pack(fill=tk.X, pady=10)

        ttk.Label(file_frame, text="Excel File:").pack(side=tk.LEFT)
        self.entry_excel = ttk.Entry(file_frame, width=50)
        self.entry_excel.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(file_frame, text="Browse", command=self._browse_excel).pack(
            side=tk.LEFT
        )
        ttk.Button(file_frame, text="Preview", command=self._preview_excel).pack(
            side=tk.LEFT, padx=5
        )

    def _create_preview_table(self, parent):
        """Data preview table"""
        self.preview_table = ttk.Treeview(parent, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(parent, orient="vertical", command=self.preview_table.yview)
        hsb = ttk.Scrollbar(
            parent, orient="horizontal", command=self.preview_table.xview
        )

        self.preview_table.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.preview_table.pack(fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

    def _create_message_section(self, parent):
        """Message composition area"""
        msg_frame = ttk.LabelFrame(parent, text="2. Compose Message")
        msg_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.txt_message = tk.Text(
            msg_frame, height=10, wrap=tk.WORD, font=("Arial", 10)
        )
        self.txt_message.pack(fill=tk.BOTH, expand=True, pady=5)

        # Attachments
        attach_frame = ttk.Frame(msg_frame)
        attach_frame.pack(fill=tk.X, pady=5)
        ttk.Button(
            attach_frame, text="📎 Attach Files", command=self._attach_files
        ).pack(side=tk.LEFT)
        self.lbl_attachments = ttk.Label(attach_frame, text="No files selected")
        self.lbl_attachments.pack(side=tk.LEFT, padx=10)

        # Preview
        preview_frame = ttk.LabelFrame(msg_frame, text="Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True)
        self.preview_text = tk.Text(preview_frame, height=4, state="disabled")
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        self.txt_message.bind("<KeyRelease>", self._update_preview)

    def _create_progress_section(self, parent):
        """Create progress tracking section"""
        progress_frame = ttk.LabelFrame(parent, text="Progress Tracking")
        progress_frame.pack(fill=tk.X, pady=10, padx=5)

        # Progress bar
        self.progress = ttk.Progressbar(
            progress_frame, orient=tk.HORIZONTAL, mode="determinate"
        )
        self.progress.pack(fill=tk.X, expand=True)

        # Status indicators
        status_frame = ttk.Frame(progress_frame)
        status_frame.pack(fill=tk.X, pady=5)

        ttk.Label(status_frame, text="Sent:").pack(side=tk.LEFT, padx=5)
        self.lbl_sent = ttk.Label(status_frame, text="0", foreground="green")
        self.lbl_sent.pack(side=tk.LEFT)

        ttk.Label(status_frame, text="Failed:").pack(side=tk.LEFT, padx=5)
        self.lbl_failed = ttk.Label(status_frame, text="0", foreground="red")
        self.lbl_failed.pack(side=tk.LEFT)

        ttk.Label(status_frame, text="Remaining:").pack(side=tk.LEFT, padx=5)
        self.lbl_remaining = ttk.Label(status_frame, text="0")
        self.lbl_remaining.pack(side=tk.LEFT)

        self.btn_stop = ttk.Button(
            status_frame,
            text="⛔ Stop",
            command=self._stop_sending,
            state="disabled",
            style="danger.TButton",
        )
        self.btn_stop.pack(side=tk.RIGHT)

    def _create_control_buttons(self, parent):
        """Control buttons"""
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=10)
        self.btn_start = ttk.Button(
            control_frame, text="🚀 Start Sending", command=self._start_sending
        )
        self.btn_start.pack(side=tk.RIGHT)
        self.btn_stop = ttk.Button(
            control_frame, text="⛔ Stop", command=self._stop_sending, state="disabled"
        )
        self.btn_stop.pack(side=tk.RIGHT, padx=5)

    def _check_session(self):
        """Verify WhatsApp session status with retries"""

        def check():
            for attempt in range(3):
                try:
                    self.session_indicator.config(text="🟡 Checking Session...")
                    client = WhatsAppClient()

                    # Check multiple elements to confirm session
                    chat_list = client.driver.find_elements(
                        By.XPATH, '//div[@aria-label="Chat list"]'
                    )
                    header = client.driver.find_elements(
                        By.XPATH, '//header[@data-testid="chatlist-header"]'
                    )

                    if chat_list and header:
                        self.session_indicator.config(
                            text="🟢 Session Active", foreground="green"
                        )
                        del client
                        return
                    del client
                except Exception as e:
                    logging.error(
                        f"Session check failed (attempt {attempt+1}): {str(e)}"
                    )
                    time.sleep(2)
            self.session_indicator.config(
                text="🔴 Authentication Required", foreground="red"
            )
            messagebox.showinfo(
                "Authentication Required",
                "Please scan the QR code to authenticate your session.",
            )

        threading.Thread(target=check, daemon=True).start()

    def _browse_excel(self):
        """Handle Excel file selection"""
        file = filedialog.askopenfilename(
            filetypes=[("Excel Files", "*.xlsx"), ("CSV Files", "*.csv")]
        )
        if file:
            self.entry_excel.delete(0, tk.END)
            self.entry_excel.insert(0, file)
            self._preview_excel()

    def _preview_excel(self):
        """Preview Excel data with validation"""
        try:
            df = pd.read_excel(self.entry_excel.get())

            if "Phone" not in df.columns:
                raise ValueError("Excel file must contain 'Phone' column")

            self.preview_table.delete(*self.preview_table.get_children())

            # Configure table
            self.preview_table["columns"] = list(df.columns)
            for col in df.columns:
                self.preview_table.heading(col, text=col)
                self.preview_table.column(col, width=120, anchor=tk.CENTER)

            # Populate data
            for _, row in df.head(15).iterrows():
                self.preview_table.insert("", tk.END, values=list(row))

        except Exception as e:
            messagebox.showerror("Error", f"Preview failed: {str(e)}")

    def _attach_files(self):
        """Handle file attachments with validation"""
        files = filedialog.askopenfilenames(
            title="Select Attachments",
            filetypes=[
                ("All Files", "*.*"),
                ("Images", "*.jpg *.jpeg *.png"),
                ("Documents", "*.pdf *.docx *.xlsx"),
            ],
        )
        if files:
            try:
                validate_attachments(files)
                self.attachments.extend(files)
                display_text = (
                    f"{len(files)} files selected"
                    if len(files) <= 3
                    else f"{len(files)} files selected: {', '.join(files[:3])}..."
                )
                self.lbl_attachments.config(text=display_text)
                self._update_preview()
            except Exception as e:
                messagebox.showerror("Attachment Error", str(e))

    def _update_preview(self, event=None):
        """Update message preview panel"""
        self.preview_text.config(state="normal")
        self.preview_text.delete(1.0, tk.END)

        message = self.txt_message.get("1.0", tk.END).strip()
        if message:
            preview = message[:500] + ("..." if len(message) > 500 else "")
            self.preview_text.insert(tk.END, "Message Preview:\n" + preview)

        if self.attachments:
            self.preview_text.insert(tk.END, "\n\nAttachments:")
            for f in self.attachments:
                self.preview_text.insert(tk.END, f"\n• {os.path.basename(f)}")

        self.preview_text.config(state="disabled")

    def _start_sending(self):
        """Start sending process in background thread"""
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._should_stop = False
        threading.Thread(target=self._send_messages, daemon=True).start()

    def _send_messages(self):
        """Main sending logic with enhanced error handling"""
        try:
            if not self._validate_inputs():
                return

            df = pd.read_excel(self.entry_excel.get())
            raw_numbers = df["Phone"].tolist()
            contacts = validate_phone_numbers(raw_numbers)

            if not contacts:
                messagebox.showwarning("Error", "No valid phone numbers found")
                return

            total = len(contacts)
            success = 0
            failed = 0
            start_time = time.time()

            client = WhatsAppClient()

            try:
                for idx, phone in enumerate(contacts, 1):
                    if self._should_stop:
                        break

                    try:
                        message = self.txt_message.get("1.0", tk.END).strip()
                        result = client.send_message(phone, message, self.attachments)

                        if result:
                            success += 1
                            logging.info(f"Sent to {phone}")
                        else:
                            failed += 1
                            logging.warning(f"Failed to send to {phone}")

                    except Exception as e:
                        failed += 1
                        logging.error(f"Error sending to {phone}: {str(e)}")
                        client._capture_screenshot(f"error_{phone}")

                    # Update UI
                    self._update_progress(idx, total, success, failed)

                    # Randomized delay to avoid detection
                    delay = random.uniform(10, 20)  # Increase delay range
                    time.sleep(delay)

                # Final report
                self._show_completion(success, failed, total, time.time() - start_time)

            finally:
                del client  # Force cleanup

        except Exception as e:
            logging.critical(f"Critical error: {str(e)}")
            messagebox.showerror("Error", f"Operation failed:\n{str(e)}")
        finally:
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")

    def _validate_inputs(self):
        """Validate all user inputs"""
        errors = []

        # Excel validation
        if not os.path.exists(self.entry_excel.get()):
            errors.append("Excel file not found")
        else:
            try:
                df = pd.read_excel(self.entry_excel.get())
                if "Phone" not in df.columns:
                    errors.append("Excel file must contain 'Phone' column")
                elif df["Phone"].isnull().all():
                    errors.append("Phone column contains no valid numbers")
            except Exception as e:
                errors.append(f"Invalid Excel file: {str(e)}")

        # Message validation
        try:
            message = self.txt_message.get("1.0", tk.END).strip()
            validate_message(message)
        except ValueError as e:
            errors.append(str(e))

        # Attachments validation
        try:
            validate_attachments(self.attachments)
        except (ValueError, FileNotFoundError) as e:
            errors.append(str(e))

        if errors:
            messagebox.showerror("Validation Errors", "\n".join(errors))
            return False

        return True

    def _update_progress(self, current, total, success, failed):
        """Update progress display with ETA"""
        progress = (current / total) * 100 if total > 0 else 0
        remaining = total - current

        self.progress["value"] = progress
        self.lbl_progress.config(
            text=f"{progress:.1f}% Complete | ✅ {success} | ❌ {failed} | ⏳ {remaining}"
        )
        self.root.update_idletasks()

    def _show_completion(self, success, failed, total, duration):
        """Show completion summary dialog"""
        duration_str = time.strftime("%H:%M:%S", time.gmtime(duration))
        message = (
            f"Total Messages: {total}\n"
            f"Successfully Sent: {success}\n"
            f"Failed Attempts: {failed}\n"
            f"Time Taken: {duration_str}"
        )

        if total > 0:
            success_rate = (success / total) * 100
            message += f"\nSuccess Rate: {success_rate:.1f}%"

        if sys.platform == "win32":
            try:
                winsound.Beep(1000, 500)
            except Exception:
                pass

        messagebox.showinfo("Process Complete", message)
        self.session_indicator.config(text="🟢 Ready for New Batch", foreground="green")

    def _stop_sending(self):
        """Gracefully stop sending process"""
        if messagebox.askyesno(
            "Confirm Stop", "Are you sure you want to stop sending?"
        ):
            self._should_stop = True
            self.btn_stop.config(state="disabled")
            logging.info("Process stopped by user")

    def _on_close(self):
        """Handle window close event"""
        if messagebox.askokcancel("Quit", "Do you want to exit?"):
            self._should_stop = True
            self.root.destroy()


if __name__ == "__main__":
    app = BulkSenderApp()
    app.root.mainloop()
