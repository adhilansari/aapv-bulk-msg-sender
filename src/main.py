# src/main.py
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import pandas as pd
import time
import random
import os
from whatsapp_client import WhatsAppClient

class BulkSenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WhatsApp Bulk Sender Pro")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.setup_ui()
        self.message_queue = queue.Queue()
        self.running = False
        self.client = None
        self.current_file = None
        self.current_attachment = None
        
        # Start queue processor
        self.root.after(100, self.process_queue)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # File Selection
        ttk.Label(main_frame, text="Excel File:").grid(row=0, column=0, sticky="w")
        self.excel_entry = ttk.Entry(main_frame, width=40)
        self.excel_entry.grid(row=0, column=1, padx=5)
        ttk.Button(main_frame, text="Browse", command=self.browse_excel).grid(row=0, column=2)
        
        # Message Input
        ttk.Label(main_frame, text="Message:").grid(row=1, column=0, sticky="nw")
        self.message_text = tk.Text(main_frame, height=8, width=50, wrap=tk.WORD)
        self.message_text.grid(row=1, column=1, pady=5, sticky="w")
        
        # Attachment
        ttk.Button(main_frame, text="Attach File", command=self.attach_file).grid(row=2, column=1, sticky="w")
        self.file_label = ttk.Label(main_frame, text="No file selected")
        self.file_label.grid(row=3, column=1, sticky="w")
        
        # Progress
        self.progress = ttk.Progressbar(main_frame, orient="horizontal", mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=3, pady=10, sticky="ew")
        
        # Status
        self.status = ttk.Label(main_frame, text="Status: Ready")
        self.status.grid(row=5, column=0, columnspan=3, sticky="ew")
        
        # Control Buttons
        ttk.Button(main_frame, text="Start Sending", command=self.start_sending).grid(row=6, column=1, pady=10)
        ttk.Button(main_frame, text="Stop", command=self.stop_sending).grid(row=6, column=2)

    def browse_excel(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if file_path:
            self.excel_entry.delete(0, tk.END)
            self.excel_entry.insert(0, file_path)
            self.current_file = file_path

    def attach_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.current_attachment = file_path
            self.file_label.config(text=os.path.basename(file_path))

    def process_queue(self):
        try:
            while True:
                task = self.message_queue.get_nowait()
                if task[0] == "progress":
                    self.progress["value"] = task[1]
                elif task[0] == "status":
                    self.status.config(text=f"Status: {task[1]}")
        except queue.Empty:
            pass
        if self.running:
            self.root.after(100, self.process_queue)

    def start_sending(self):
        if not self.validate_inputs():
            return
        
        self.running = True
        threading.Thread(target=self.run_bulk_send, daemon=True).start()

    def validate_inputs(self):
        if not self.current_file:
            messagebox.showerror("Error", "Please select an Excel file!")
            return False
        if not os.path.exists(self.current_file):
            messagebox.showerror("Error", "Selected Excel file doesn't exist!")
            return False
        return True

    def run_bulk_send(self):
        try:
            self.client = WhatsAppClient()
            self.client.initialize()
            
            df = pd.read_excel(self.current_file)
            total = len(df)
            success_count = 0
            
            for index, row in df.iterrows():
                if not self.running:
                    break
                
                phone = self.process_phone_number(str(row['Phone']))
                message = self.message_text.get("1.0", tk.END).strip()
                
                if self.client.send_message(phone, message, self.current_attachment):
                    success_count += 1
                
                self.update_progress((index + 1) / total * 100)
                self.update_status(f"Sent {index+1}/{total} | Success: {success_count}")
                time.sleep(random.uniform(1.5, 3.5))
            
            self.message_queue.put(("status", "Complete"))
            messagebox.showinfo("Complete", f"Process finished!\nSuccess: {success_count}/{total}")
        
        except Exception as e:
            self.message_queue.put(("status", f"Error: {str(e)}"))
            messagebox.showerror("Error", str(e))
        finally:
            self.cleanup()

    def process_phone_number(self, phone):
        phone = phone.strip().replace(" ", "").replace("-", "")
        if not phone.startswith("+"):
            phone = f"+{phone}"
        return phone

    def update_progress(self, value):
        self.message_queue.put(("progress", value))

    def update_status(self, message):
        self.message_queue.put(("status", message))

    def stop_sending(self):
        self.running = False
        self.update_status("Stopping...")

    def cleanup(self):
        self.running = False
        if self.client:
            self.client.close()
        self.update_progress(0)
        self.update_status("Ready")

    def on_close(self):
        self.stop_sending()
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("600x450")
    app = BulkSenderApp(root)
    root.mainloop()