import socket
import threading
import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import time
from tkinter import filedialog  # --- added
import base64, os               # --- added

# NEW constants
MAX_FILE_SIZE = 100 * 1024 * 1024   # 100MB
CHUNK_SIZE = 48 * 1024              # 48KB per chunk (base64 inflates ~33%)

class ChatClient:
    def __init__(self):
        self.client = None
        self.username = None
        self.connected = False
        
        # Initialize GUI
        self.root = tk.Tk()
        self.root.title("Chat Application")
        self.root.geometry("800x600")
        self.root.configure(bg='#2c3e50')
        
        self.setup_styles()
        self.current_chat = None  # 'private:username' or 'group:group_id'
        self.typing_users = set()
        
        # --- NEW: incoming file transfers state ---
        self.incoming_files = {}   # transfer_id -> {'parts':[], 'filename':..., 'is_group':bool,'sender':..., 'total':int, 'received':int, 'timestamp':str}
        
        self.show_login_screen()
    
    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure styles
        self.style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#2c3e50', foreground='white')
        self.style.configure('Heading.TLabel', font=('Arial', 12, 'bold'), background='#34495e', foreground='white')
        self.style.configure('Chat.TFrame', background='#ecf0f1')
        self.style.configure('Sidebar.TFrame', background='#34495e')
    
    def show_login_screen(self):
        # Clear the window
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Login frame
        login_frame = tk.Frame(self.root, bg='#2c3e50')
        login_frame.pack(expand=True, fill='both')
        
        # Title
        title_label = tk.Label(login_frame, text="💬 Chat Application", 
                              font=('Arial', 24, 'bold'), bg='#2c3e50', fg='white')
        title_label.pack(pady=50)
        
        # Username entry
        tk.Label(login_frame, text="Username:", font=('Arial', 12), 
                bg='#2c3e50', fg='white').pack(pady=10)
        
        self.username_entry = tk.Entry(login_frame, font=('Arial', 12), width=20)
        self.username_entry.pack(pady=10)
        self.username_entry.bind('<Return>', lambda e: self.login())
        
        # Buttons frame
        button_frame = tk.Frame(login_frame, bg='#2c3e50')
        button_frame.pack(pady=20)
        
        login_btn = tk.Button(button_frame, text="Login", command=self.login,
                             bg='#3498db', fg='white', font=('Arial', 12, 'bold'),
                             width=10, relief='flat')
        login_btn.pack(side='left', padx=10)
        
        register_btn = tk.Button(button_frame, text="Register", command=self.register,
                                bg='#27ae60', fg='white', font=('Arial', 12, 'bold'),
                                width=10, relief='flat')
        register_btn.pack(side='left', padx=10)
        
        self.username_entry.focus()
    
    def connect_to_server(self):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print("Attempting to connect to server...")
            self.client.connect(('localhost', 12345))
            self.connected = True
            print("Connected to server successfully!")
            
            # Start listening for messages
            listen_thread = threading.Thread(target=self.listen_for_messages)
            listen_thread.daemon = True
            listen_thread.start()
            
            return True
        except ConnectionRefusedError:
            messagebox.showerror("Connection Error", "Server is not running!\nPlease start the server first.")
            return False
        except socket.error as e:
            messagebox.showerror("Connection Error", f"Could not connect to server!\nError: {e}")
            return False
        except Exception as e:
            messagebox.showerror("Connection Error", f"Unexpected error: {e}")
            return False
    
    def login(self):
        username = self.username_entry.get().strip()
        if not username:
            messagebox.showerror("Error", "Please enter a username")
            return
        
        if not self.connected and not self.connect_to_server():
            return
        
        # Send login request
        login_data = {'action': 'login', 'username': username}
        self.send_message(login_data)
    
    def register(self):
        username = self.username_entry.get().strip()
        if not username:
            messagebox.showerror("Error", "Please enter a username")
            return
        
        if not self.connected and not self.connect_to_server():
            return
        
        # Send register request
        register_data = {'action': 'register', 'username': username}
        self.send_message(register_data)
    
    def show_main_interface(self, profile):
        self.username = profile.get('nickname', self.username_entry.get())
        
        # Clear the window
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Main container
        main_container = tk.Frame(self.root)
        main_container.pack(fill='both', expand=True)
        
        # Left sidebar
        self.setup_sidebar(main_container)
        
        # Right chat area
        self.setup_chat_area(main_container)
        
        # Load initial data
        self.refresh_contacts()
        self.refresh_groups()
    
    def setup_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg='#34495e', width=250)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        
        # Profile section
        profile_frame = tk.Frame(sidebar, bg='#34495e')
        profile_frame.pack(fill='x', padx=10, pady=10)
        
        self.avatar_label = tk.Label(profile_frame, text="👤", font=('Arial', 24),
                                    bg='#34495e', fg='white')
        self.avatar_label.pack(side='left')
        
        profile_info = tk.Frame(profile_frame, bg='#34495e')
        profile_info.pack(side='left', fill='x', expand=True, padx=10)
        
        self.nickname_label = tk.Label(profile_info, text=self.username, 
                                      font=('Arial', 12, 'bold'), bg='#34495e', fg='white')
        self.nickname_label.pack(anchor='w')
        
        self.status_label = tk.Label(profile_info, text="🟢 Online", 
                                    font=('Arial', 10), bg='#34495e', fg='#2ecc71')
        self.status_label.pack(anchor='w')
        
        # Profile button
        profile_btn = tk.Button(profile_frame, text="⚙️", command=self.edit_profile,
                               bg='#34495e', fg='white', relief='flat', font=('Arial', 12))
        profile_btn.pack(side='right')
        
        # Tabs for contacts and groups
        notebook = ttk.Notebook(sidebar)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Contacts tab
        contacts_frame = tk.Frame(notebook, bg='#34495e')
        notebook.add(contacts_frame, text='Contacts')
        
        # Add contact button
        add_contact_btn = tk.Button(contacts_frame, text="+ Add Contact", 
                                   command=self.add_contact_dialog,
                                   bg='#3498db', fg='white', relief='flat')
        add_contact_btn.pack(fill='x', padx=5, pady=5)
        
        # --- added remove contact button ---
        remove_contact_btn = tk.Button(contacts_frame, text="- Remove Contact",
                                       command=self.remove_contact_dialog,
                                       bg='#e74c3c', fg='white', relief='flat')
        remove_contact_btn.pack(fill='x', padx=5, pady=(0,5))
        # --- end addition ---
        
        # Contacts list
        contacts_list_frame = tk.Frame(contacts_frame, bg='#34495e')
        contacts_list_frame.pack(fill='both', expand=True, padx=5)
        
        self.contacts_listbox = tk.Listbox(contacts_list_frame, bg='#ecf0f1', 
                                          selectbackground='#3498db', font=('Arial', 10))
        scrollbar1 = tk.Scrollbar(contacts_list_frame, orient='vertical')
        
        self.contacts_listbox.config(yscrollcommand=scrollbar1.set)
        scrollbar1.config(command=self.contacts_listbox.yview)
        
        self.contacts_listbox.pack(side='left', fill='both', expand=True)
        scrollbar1.pack(side='right', fill='y')
        
        self.contacts_listbox.bind('<Double-1>', self.open_private_chat)
        
        # Groups tab
        groups_frame = tk.Frame(notebook, bg='#34495e')
        notebook.add(groups_frame, text='Groups')
        
        # Group buttons
        group_buttons_frame = tk.Frame(groups_frame, bg='#34495e')
        group_buttons_frame.pack(fill='x', padx=5, pady=5)
        
        create_group_btn = tk.Button(group_buttons_frame, text="+ Create", 
                                    command=self.create_group_dialog,
                                    bg='#27ae60', fg='white', relief='flat', font=('Arial', 9))
        create_group_btn.pack(side='left', fill='x', expand=True, padx=2)
        
        join_group_btn = tk.Button(group_buttons_frame, text="Join", 
                                  command=self.join_group_dialog,
                                  bg='#f39c12', fg='white', relief='flat', font=('Arial', 9))
        join_group_btn.pack(side='right', fill='x', expand=True, padx=2)
        
        # Groups list
        groups_list_frame = tk.Frame(groups_frame, bg='#34495e')
        groups_list_frame.pack(fill='both', expand=True, padx=5)
        
        self.groups_listbox = tk.Listbox(groups_list_frame, bg='#ecf0f1', 
                                        selectbackground='#27ae60', font=('Arial', 10))
        scrollbar2 = tk.Scrollbar(groups_list_frame, orient='vertical')
        
        self.groups_listbox.config(yscrollcommand=scrollbar2.set)
        scrollbar2.config(command=self.groups_listbox.yview)
        
        self.groups_listbox.pack(side='left', fill='both', expand=True)
        scrollbar2.pack(side='right', fill='y')
        
        self.groups_listbox.bind('<Double-1>', self.open_group_chat)
    
    def setup_chat_area(self, parent):
        chat_container = tk.Frame(parent, bg='#ecf0f1')
        chat_container.pack(side='right', fill='both', expand=True)
        
        # Chat header
        self.chat_header = tk.Frame(chat_container, bg='#3498db', height=50)
        self.chat_header.pack(fill='x')
        self.chat_header.pack_propagate(False)
        
        self.chat_title_label = tk.Label(self.chat_header, text="Select a contact or group to start chatting",
                                        font=('Arial', 14, 'bold'), bg='#3498db', fg='white')
        self.chat_title_label.pack(expand=True)
        
        # NEW buttons (hidden until group selected)
        self.add_member_btn = tk.Button(self.chat_header, text="Add Member",
                                        command=self.add_member_to_group_dialog,
                                        bg='#2980b9', fg='white', font=('Arial', 10), relief='flat')
        self.add_member_btn.pack(side='right', padx=6)
        self.add_member_btn.pack_forget()
        
        self.leave_group_btn = tk.Button(self.chat_header, text="Leave",
                                         command=self.leave_current_group,
                                         bg='#e74c3c', fg='white', font=('Arial', 10), relief='flat')
        self.leave_group_btn.pack(side='right', padx=6)
        self.leave_group_btn.pack_forget()
        
        # Chat messages area
        messages_frame = tk.Frame(chat_container, bg='#ecf0f1')
        messages_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.messages_text = tk.Text(messages_frame, bg='white', font=('Arial', 11),
                                    wrap='word', state='disabled')
        scrollbar3 = tk.Scrollbar(messages_frame, orient='vertical')
        
        self.messages_text.config(yscrollcommand=scrollbar3.set)
        scrollbar3.config(command=self.messages_text.yview)
        
        self.messages_text.pack(side='left', fill='both', expand=True)
        scrollbar3.pack(side='right', fill='y')
        
        # Typing indicator
        self.typing_label = tk.Label(chat_container, text="", font=('Arial', 9, 'italic'),
                                    bg='#ecf0f1', fg='#7f8c8d')
        self.typing_label.pack(fill='x', padx=10)
        
        # Message input area
        input_frame = tk.Frame(chat_container, bg='#ecf0f1')
        input_frame.pack(fill='x', padx=10, pady=10)
        attach_btn = tk.Button(input_frame, text="📎", command=self.attach_file,
                               bg='#34495e', fg='white', font=('Arial',12), relief='flat', width=3)
        attach_btn.pack(side='left', padx=(0,6))
        
        self.message_entry = tk.Entry(input_frame, font=('Arial', 12))
        self.message_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.message_entry.bind('<Return>', self.send_current_message)
        self.message_entry.bind('<KeyPress>', self.on_typing)
        
        send_btn = tk.Button(input_frame, text="Send", command=self.send_current_message,
                            bg='#3498db', fg='white', font=('Arial', 12, 'bold'), relief='flat')
        send_btn.pack(side='right')
        
        self.message_entry.config(state='disabled')
