# Author: Guilherme Cugler
# GitHub: guilhermecugler
# Email: guilhermecugler@gmail.com
# Contact: +5513997230761 (WhatsApp)

import customtkinter as ctk
import os
import json
import threading
from tkinter import messagebox
from datetime import datetime
from auth.login import run_async_login
from processing.processor import process_ids, load_processed_ids, save_processed_ids

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class InstagramTool(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Instagram - Close Friends Manager")
        window_height = 671
        window_width = 711

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        position_top = int(screen_height / 2 - window_height / 2)
        position_right = int(screen_width / 2 - window_width / 2)

        self.geometry(f'{window_width}x{window_height}+{position_right}+{position_top-24}')

        self.current_user = None
        self.processed_ids = {"added": [], "removed": []}
        self.running = False
        self.loaded_session = None

        self.create_widgets()
        self.load_sessions()

    def create_widgets(self):
        # Session Management
        self.session_frame = ctk.CTkFrame(self)
        self.session_frame.pack(pady=10, padx=10, fill="x")
        
        self.session_label = ctk.CTkLabel(self.session_frame, text="Saved Sessions:")
        self.session_label.pack(side="left", padx=5)
        
        self.session_combobox = ctk.CTkComboBox(self.session_frame, values=[''])
        self.session_combobox.pack(side="left", padx=5, fill="x", expand=True)
        
        self.load_btn = ctk.CTkButton(self.session_frame, text="Load", command=self.load_session)
        self.load_btn.pack(side="left", padx=5)
        
        # Login Section
        self.login_frame = ctk.CTkFrame(self)
        self.login_frame.pack(pady=10, padx=10, fill="x")
        
        self.username_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Instagram Username")
        self.username_entry.pack(pady=5, padx=5, fill="x")
        
        self.password_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Password", show="*")
        self.password_entry.pack(pady=5, padx=5, fill="x")
        
        self.login_btn = ctk.CTkButton(
            self.login_frame, 
            text="Login & Save Session", 
            command=self.start_login
        )
        self.login_btn.pack(pady=5)
        
        # Operation Controls
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.pack(pady=10, padx=10, fill="x")
        
        self.mode_var = ctk.StringVar(value="add")
        ctk.CTkRadioButton(
            self.controls_frame, 
            text="Add", 
            variable=self.mode_var, 
            value="add"
        ).pack(side="left", padx=5)
        
        ctk.CTkRadioButton(
            self.controls_frame, 
            text="Remove", 
            variable=self.mode_var, 
            value="remove"
        ).pack(side="left", padx=5)
        
        self.resume_var = ctk.BooleanVar()
        ctk.CTkCheckBox(
            self.controls_frame,
            text="Resume from where left off",
            variable=self.resume_var
        ).pack(side="left", padx=5)
        
        self.start_btn = ctk.CTkButton(
            self.controls_frame, 
            text="Start Processing", 
            command=self.start_processing
        )
        self.start_btn.pack(side="right", padx=5)
        
        # Log Console
        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        self.log_text = ctk.CTkTextbox(self.log_frame, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self, mode="indeterminate")
        self.progress_bar.pack(pady=10, padx=10, fill="x")
        self.author_label = ctk.CTkLabel(self, text="Author: Guilherme Cugler - @guilhermecugler", anchor="w")
        self.author_label.pack(side="bottom", fill="x", padx=10, pady=5)
        # Status Bar
        self.status_bar = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status_bar.pack(side="bottom", fill="x", padx=10, pady=5)



    def load_sessions(self):
        session_dir = "sessions"
        if not os.path.exists(session_dir):
            os.makedirs(session_dir)

        session_files = [
            f.replace("_session.json", "") 
            for f in os.listdir(session_dir) 
            if f.endswith("_session.json")
        ]

        self.session_combobox.configure(values=session_files)

    def log(self, message, color=None):  # color=None significa cor padrão
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"

        # Inserir o texto
        self.log_text.insert("end", formatted_message)

        # Aplicar a tag apenas se uma cor for fornecida
        if color:
            tag_name = f"color_{color}"  # Nome único para a tag
            self.log_text.tag_config(tag_name, foreground=color)
            self.log_text.tag_add(tag_name, "end-2c linestart", "end-1c")

        # Rolar para o final
        self.log_text.see("end")
        self.update()

    def update_status(self, message):
        self.status_bar.configure(text=message)
        self.update()

    def load_session(self):
        session_name = self.session_combobox.get()
        if not session_name:
            return

        try:
            with open(f"sessions/{session_name}_session.json", "r") as f:
                self.loaded_session = json.load(f)
                self.current_user = session_name
                self.update_status(f"Session loaded: {session_name}")
                self.log(f"Session '{session_name}' loaded successfully", color="green")
                self.processed_ids = load_processed_ids(self.current_user)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load session: {str(e)}")

    def start_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        if not username or not password:
            messagebox.showwarning("Warning", "Please fill in username and password!")
            return

        threading.Thread(
            target=run_async_login, 
            args=(username, password, self), 
            daemon=True
        ).start()

    def start_processing(self):
        if not self.loaded_session:
            messagebox.showwarning("Warning", "Load a session first!")
            return

        self.running = True
        mode = self.mode_var.get()
        resume = self.resume_var.get()

        self.progress_bar.start()
        threading.Thread(target=self.run_processing, args=(mode, resume), daemon=True).start()

    def run_processing(self, mode, resume):
        process_ids(self, mode, resume)
        self.progress_bar.stop()

    def on_closing(self):
        if self.running:
            self.running = False
            self.update_status("Finishing operation...")
            self.after(2000, self.destroy)
        else:
            self.destroy()
