import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import winsound
from ttkbootstrap import Style
import pandas as pd
import logging
import logging.handlers
import threading
import random
import time
from selenium.webdriver.common.by import By
import os
import sys
from core.client import WhatsAppClient
from utils.validator import (
    validate_phone_numbers,
    validate_message,
    validate_attachments,
)


class BulkSenderApp:
    def __init__(self):
        self.root = Style(theme="minty").master
        self.root.title("WhatsApp Bulk Messenger Pro")
        self.root.geometry("1200x900")
        self.attachments = []
        self._should_stop = False
        self._setup_logging()
        self._setup_ui()
        self._check_session()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_logging(self):
        """Configure logging system"""
        os.makedirs("logs", exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            "logs/app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[handler],
        )

    def _setup_ui(self):
        """Initialize user interface components"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

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

    def _create_session_panel(self, parent):
        """Session status components"""
        session_frame = ttk.Frame(parent)
        session_frame.pack(fill=tk.X, pady=5)

        self.session_indicator = ttk.Label(
            session_frame,
            text="🟠 Session Status: Initializing...",
            font=("Helvetica", 10, "bold"),
        )
        self.session_indicator.pack(side=tk.LEFT)

        ttk.Button(
            session_frame, text="Refresh Session", command=self._check_session
        ).pack(side=tk.RIGHT)

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
        """Progress indicators"""
        self.progress = ttk.Progressbar(parent, orient="horizontal", mode="determinate")
        self.progress.pack(fill=tk.X, pady=10)
        self.lbl_progress = ttk.Label(
            parent, text="0% Complete | Sent: 0 | Failed: 0 | Remaining: 0"
        )
        self.lbl_progress.pack()

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
                self.attachments = list(files)
                self.lbl_attachments.config(text=f"{len(files)} files selected")
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
