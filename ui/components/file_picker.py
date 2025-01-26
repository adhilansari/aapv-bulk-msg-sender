import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from ttkbootstrap import Style

class FilePicker(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.selected_files = []
        self._create_widgets()
        
    def _create_widgets(self):
        self.btn_browse = ttk.Button(
            self,
            text="📁 Attach Files",
            command=self._browse_files,
            style="primary.TButton"
        )
        self.btn_browse.pack(side=tk.LEFT, padx=5)
        
        self.lbl_files = ttk.Label(self, text="No files selected")
        self.lbl_files.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _browse_files(self):
        files = filedialog.askopenfilenames(
            title="Select Files",
            filetypes=[
                ("All Files", "*.*"),
                ("Images", "*.jpg *.png *.gif"),
                ("Documents", "*.pdf *.docx")
            ]
        )
        if files:
            self.selected_files = list(files)
            self.lbl_files.config(text=f"{len(files)} files selected")

    def get_files(self):
        return self.selected_files