import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ttkbootstrap import Style
import pandas as pd
import logging
import logging.handlers
import threading
import random
import time
import winsound
import os
from core.client import WhatsAppClient
from utils.validator import validate_phone_numbers

class BulkSenderApp:
    def __init__(self):
        self.root = Style(theme='minty').master
        self.root.title("WhatsApp Bulk Messenger Pro")
        self.root.geometry("1000x800")
        self.attachments = []
        self._should_stop = False
        self._setup_logging()
        self._setup_ui()
        self._check_session()

    def _setup_logging(self):
        """Configure logging with rotation"""
        os.makedirs("logs", exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            'logs/app.log',
            maxBytes=2*1024*1024,  # 2MB
            backupCount=3,
            encoding='utf-8'
        )
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[handler, logging.StreamHandler()]
        )

    def _setup_ui(self):
        """Initialize user interface"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="Step 1: Select Contacts File")
        file_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(file_frame, text="Excel File:").pack(side=tk.LEFT)
        self.entry_excel = ttk.Entry(file_frame, width=40)
        self.entry_excel.pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Browse", command=self._browse_excel).pack(side=tk.LEFT)
        ttk.Button(file_frame, text="Preview", command=self._preview_excel).pack(side=tk.LEFT, padx=5)

        # Preview table
        self.preview_table = ttk.Treeview(main_frame, show='headings')
        vsb = ttk.Scrollbar(main_frame, orient="vertical", command=self.preview_table.yview)
        hsb = ttk.Scrollbar(main_frame, orient="horizontal", command=self.preview_table.xview)
        self.preview_table.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.preview_table.pack(fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # Message composition
        msg_frame = ttk.LabelFrame(main_frame, text="Step 2: Compose Message")
        msg_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.txt_message = tk.Text(msg_frame, height=8, wrap=tk.WORD)
        self.txt_message.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Attachments
        attach_frame = ttk.Frame(msg_frame)
        attach_frame.pack(fill=tk.X, pady=5)
        ttk.Button(attach_frame, text="📎 Attach Files", command=self._attach_files).pack(side=tk.LEFT)
        self.lbl_attachments = ttk.Label(attach_frame, text="No files selected")
        self.lbl_attachments.pack(side=tk.LEFT, padx=10)

        # Progress
        self.progress = ttk.Progressbar(main_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill=tk.X, pady=10)
        self.lbl_progress = ttk.Label(main_frame, text="0% Complete | Sent: 0 | Failed: 0")
        self.lbl_progress.pack()

        # Controls
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        self.btn_start = ttk.Button(control_frame, text="🚀 Start Sending", command=self._start_sending)
        self.btn_start.pack(side=tk.RIGHT)
        self.btn_stop = ttk.Button(control_frame, text="⛔ Stop", command=self._stop_sending, state="disabled")
        self.btn_stop.pack(side=tk.RIGHT, padx=5)

        # Status
        self.status_bar = ttk.Label(main_frame, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _browse_excel(self):
        """Handle Excel file selection"""
        file = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if file:
            self.entry_excel.delete(0, tk.END)
            self.entry_excel.insert(0, file)
            self._preview_excel()

    def _preview_excel(self):
        """Preview Excel file contents"""
        try:
            df = pd.read_excel(self.entry_excel.get())
            self.preview_table.delete(*self.preview_table.get_children())
            
            self.preview_table["columns"] = list(df.columns)
            for col in df.columns:
                self.preview_table.heading(col, text=col)
                self.preview_table.column(col, width=100)
                
            for _, row in df.head(10).iterrows():
                self.preview_table.insert("", tk.END, values=list(row))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to preview file:\n{str(e)}")

    def _attach_files(self):
        """Handle file attachments"""
        files = filedialog.askopenfilenames()
        if files:
            self.attachments = list(files)
            self.lbl_attachments.config(text=f"{len(files)} files selected")

    def _start_sending(self):
        """Start sending process"""
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._should_stop = False
        threading.Thread(target=self._send_messages, daemon=True).start()

    def _send_messages(self):
        """Main sending logic"""
        try:
            if not self._validate_inputs():
                return

            df = pd.read_excel(self.entry_excel.get())
            contacts = validate_phone_numbers(df['Phone'])
            
            if not contacts:
                messagebox.showwarning("Error", "No valid phone numbers found")
                return

            total = len(contacts)
            success = 0
            failed = 0
            
            client = WhatsAppClient()
            
            try:
                for idx, phone in enumerate(contacts, 1):
                    if self._should_stop:
                        break
                    
                    try:
                        message = self.txt_message.get("1.0", tk.END).strip()
                        if client.send_message(phone, message, self.attachments):
                            success += 1
                        else:
                            failed += 1
                    except Exception as e:
                        failed += 1
                        logging.error(f"Error sending to {phone}: {str(e)}")
                    
                    self._update_progress(idx, total, success, failed)
                    time.sleep(random.uniform(5, 15))
                
                self._show_completion(success, failed, total)
            
            finally:
                del client  # Force cleanup
            
        except Exception as e:
            logging.critical(f"Critical error: {str(e)}")
            messagebox.showerror("Error", f"Operation failed:\n{str(e)}")
        finally:
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")

    def _validate_inputs(self):
        """Validate user inputs"""
        if not os.path.exists(self.entry_excel.get()):
            messagebox.showerror("Error", "Excel file not found")
            return False
            
        try:
            pd.read_excel(self.entry_excel.get())
        except Exception as e:
            messagebox.showerror("Error", f"Invalid Excel file: {str(e)}")
            return False
            
        if not self.txt_message.get("1.0", tk.END).strip() and not self.attachments:
            messagebox.showerror("Error", "Message or attachment required")
            return False
            
        return True

    def _update_progress(self, current, total, success, failed):
        """Update progress display"""
        progress = (current / total) * 100 if total > 0 else 0
        self.progress["value"] = progress
        self.lbl_progress.config(
            text=f"{progress:.1f}% Complete | ✅ {success} | ❌ {failed} | ⏳ {max(0, total-current)}"
        )
        self.root.update_idletasks()

    def _show_completion(self, success, failed, total):
        """Show completion dialog"""
        winsound.Beep(1000, 500)
        message = f"Sent: {success}\nFailed: {failed}"
        if total > 0:
            message += f"\nSuccess rate: {(success/total)*100:.1f}%"
        messagebox.showinfo("Process Complete", message)

    def _stop_sending(self):
        """Stop sending process"""
        self._should_stop = True
        self.btn_stop.config(state="disabled")
        logging.info("Process stopped by user")

    def _check_session(self):
        """Check WhatsApp session status"""
        def check():
            try:
                client = WhatsAppClient()
                del client
                self.status_bar.config(text="Ready to send", foreground="green")
            except Exception as e:
                self.status_bar.config(text="Scan QR code in browser", foreground="orange")

        threading.Thread(target=check, daemon=True).start()

if __name__ == "__main__":
    app = BulkSenderApp()
    app.root.mainloop()