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
        self.current_chat = None  
        self.typing_users = set()
        
        
        self.incoming_files = {}   
        
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
            self.client.connect(('26.238.174.186', 12345))
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
    
    def send_message(self, data):
        if self.connected:
            try:
                message = json.dumps(data) + "\n"   # newline-delimited frame
                self.client.send(message.encode('utf-8'))
            except:
                self.connected = False
                messagebox.showerror("Error", "Connection lost!")
    
    def listen_for_messages(self):
        buffer = ""
        while self.connected:
            try:
                chunk = self.client.recv(4096).decode('utf-8')
                if not chunk:
                    break
                buffer += chunk
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except:
                        continue
                    self.process_incoming_message(data)
            except:
                break
        self.connected = False
    
    def process_incoming_message(self, data):
        if 'success' in data:
            if data['success']:
                if 'profile' in data:  # login or profile-related response
                    if 'new_username' in data:
                        # username changed
                        self.username = data['new_username']
                        self.nickname_label.config(text=data['profile'].get('nickname', self.username))
                    self.root.after(0, self.show_main_interface, data['profile'])
                else:
                    msg_txt = (data.get('message') or '').lower()
                    if msg_txt.startswith('message sent'): return
                    if msg_txt.startswith('message sent to group'): return
                    messagebox.showinfo("Success", data['message'])
            else:
                messagebox.showerror("Error", data['message'])
            return
        
        elif 'results' in data:
            # Search results
            self.show_search_results(data['results'])
        
        elif 'contacts' in data:
            # Contacts list
            self.update_contacts_list(data['contacts'])
        
        elif 'groups' in data:
            # Groups list
            self.update_groups_list(data['groups'])
        
        elif data.get('type') == 'private_message':
            # Incoming private message
            self.root.after(0, self.display_private_message, data)
        
        elif data.get('type') == 'group_message':
            # Incoming group message
            self.root.after(0, self.display_group_message, data)
        
        elif data.get('type') == 'group_notification':
            # Group notification
            self.root.after(0, self.display_group_notification, data)
        
        elif data.get('type') == 'typing_indicator':
            # Typing indicator
            self.root.after(0, self.update_typing_indicator, data)
        
        elif data.get('type') == 'status_update':
            # Status update
            self.root.after(0, self.update_contact_status, data)
        
        elif data.get('type') == 'group_added':
            # You were added to a group
            messagebox.showinfo("Group", f"You were added to group: {data['name']}")
            self.refresh_groups()
        
        elif data.get('type') == 'profile_update':
            self.handle_profile_update_event(data)
        
        elif data.get('type') == 'username_changed':
            self.handle_username_changed_event(data)
        elif data.get('type') == 'file_message':
            self.root.after(0, self.display_file_message, data, False)
        elif data.get('type') == 'group_file_message':
            self.root.after(0, self.display_file_message, data, True)
        # --- NEW chunked file protocol handling ---
        elif data.get('type') in ('file_start','group_file_start'):
            self.root.after(0, self.handle_file_start, data)
        elif data.get('type') in ('file_chunk','group_file_chunk'):
            self.root.after(0, self.handle_file_chunk, data)
        elif data.get('type') in ('file_end','group_file_end'):
            self.root.after(0, self.handle_file_end, data)
    
    # NEW handlers for profile & username events
    def handle_profile_update_event(self, data):
        uname = data['username']
        # Update own profile display
        if uname == self.username:
            self.avatar_label.config(text=data['avatar'])
            self.nickname_label.config(text=data['nickname'])
        # Update contacts entry text if present
        if hasattr(self, 'contacts_data'):
            to_update_index = None
            for idx, c in self.contacts_data.items():
                if c['username'] == uname:
                    self.contacts_data[idx]['nickname'] = data['nickname']
                    self.contacts_data[idx]['avatar'] = data['avatar']
                    self.contacts_data[idx]['status'] = data['status']
                    to_update_index = idx
                    break
            if to_update_index is not None:
                self.refresh_contacts()

    def handle_username_changed_event(self, data):
        old = data['old_username']; new = data['new_username']
        # Update contacts_data
        changed = False
        if hasattr(self, 'contacts_data'):
            for idx, c in list(self.contacts_data.items()):
                if c['username'] == old:
                    c['username'] = new
                    changed = True
        if changed:
            self.refresh_contacts()
        # If current private chat with old -> remap
        if self.current_chat == f"private:{old}":
            self.current_chat = f"private:{new}"
            self.chat_title_label.config(text=f"💬 {new}")
        # Groups will be refreshed on next fetch if needed
    
    #Modify profile dialog invocation to allow username change
    def edit_profile(self):
        dialog = ProfileDialog(self.root,
                               current_avatar=self.avatar_label.cget('text'),
                               current_nickname=self.nickname_label.cget('text'),
                               current_username=self.username)
        if dialog.result:
            new_avatar, new_nickname, new_username = dialog.result
            # send profile (avatar/nickname)
            self.send_message({
                'action': 'update_profile',
                'profile': {'avatar': new_avatar, 'nickname': new_nickname}
            })
            # send username change if changed
            if new_username and new_username != self.username:
                self.send_message({'action':'change_username','new_username':new_username})
            # optimistic UI
            self.avatar_label.config(text=new_avatar)
            self.nickname_label.config(text=new_nickname)
    
    def add_contact_dialog(self):
        username = simpledialog.askstring("Add Contact", "Enter username to add:")
        if username:
            add_data = {'action': 'add_contact', 'username': username}
            self.send_message(add_data)
            # Refresh contacts after adding
            self.root.after(1000, self.refresh_contacts)
    
    def create_group_dialog(self):
        group_name = simpledialog.askstring("Create Group", "Enter group name:")
        if group_name:
            create_data = {'action': 'create_group', 'group_name': group_name}
            self.send_message(create_data)
            # Refresh groups after creating
            self.root.after(1000, self.refresh_groups)
    
    def join_group_dialog(self):
        group_id = simpledialog.askstring("Join Group", "Enter group ID:")
        if group_id:
            join_data = {'action': 'join_group', 'group_id': group_id}
            self.send_message(join_data)
            # Refresh groups after joining
            self.root.after(1000, self.refresh_groups)
    
    def refresh_contacts(self):
        self.send_message({'action': 'get_contacts'})
    
    def refresh_groups(self):
        self.send_message({'action': 'get_groups'})
    
    def update_contacts_list(self, contacts):
        self.contacts_listbox.delete(0, tk.END)
        self.contacts_data = {}
        
        for contact in contacts:
            status_emoji = "🟢" if contact['status'] == 'online' else "⚫"
            display_text = f"{contact['avatar']} {contact['nickname']} {status_emoji}"
            self.contacts_listbox.insert(tk.END, display_text)
            self.contacts_data[len(self.contacts_data)] = contact
    
    def update_groups_list(self, groups):
        self.groups_listbox.delete(0, tk.END)
        self.groups_data = {}
        
        for group in groups:
            display_text = f"👥 {group['name']} ({group['member_count']})"
            self.groups_listbox.insert(tk.END, display_text)
            self.groups_data[len(self.groups_data)] = group
    
    def open_private_chat(self, event):
        selection = self.contacts_listbox.curselection()
        if selection:
            contact = self.contacts_data[selection[0]]
            self.current_chat = f"private:{contact['username']}"
            self.chat_title_label.config(text=f"💬 {contact['nickname']}")
            self.clear_messages()
            self.message_entry.config(state='normal')
            self.message_entry.focus()
            self.add_member_btn.pack_forget()
            self.leave_group_btn.pack_forget()
    
    def open_group_chat(self, event):
        selection = self.groups_listbox.curselection()
        if selection:
            group = self.groups_data[selection[0]]
            self.current_chat = f"group:{group['group_id']}"
            self.chat_title_label.config(text=f"👥 {group['name']}")
            self.clear_messages()
            self.message_entry.config(state='normal')
            self.message_entry.focus()
            
            # Show Add Member and Leave Group buttons
            self.add_member_btn.pack(side='right', padx=6)
            self.leave_group_btn.pack(side='right', padx=6)
    
    def send_current_message(self, event=None):
        if not self.current_chat:
            return
        
        message = self.message_entry.get().strip()
        if not message:
            return
        
        chat_type, chat_id = self.current_chat.split(':', 1)
        
        if chat_type == 'private':
            send_data = {
                'action': 'send_message',
                'recipient': chat_id,
                'message': message
            }
        else:  # group
            send_data = {
                'action': 'send_group_message',
                'group_id': chat_id,
                'message': message
            }
        
        self.send_message(send_data)
        self.message_entry.delete(0, tk.END)
        
        # Display own message
        self.display_own_message(message)
    
    def display_own_message(self, message):
        self.messages_text.config(state='normal')
        timestamp = time.strftime('%H:%M')
        self.messages_text.insert(tk.END, f"You ({timestamp}): {message}\n", 'own_message')
        self.messages_text.config(state='disabled')
        self.messages_text.see(tk.END)
    
    def display_private_message(self, data):
        if self.current_chat == f"private:{data['sender']}":
            self.messages_text.config(state='normal')
            self.messages_text.insert(tk.END, f"{data['avatar']} {data['sender']} ({data['timestamp']}): {data['message']}\n", 'received_message')
            self.messages_text.config(state='disabled')
            self.messages_text.see(tk.END)
    
    def display_group_message(self, data):
        if self.current_chat == f"group:{data['group_id']}":
            self.messages_text.config(state='normal')
            self.messages_text.insert(tk.END, f"{data['avatar']} {data['sender']} ({data['timestamp']}): {data['message']}\n", 'received_message')
            self.messages_text.config(state='disabled')
            self.messages_text.see(tk.END)
    
    def display_group_notification(self, data):
        if self.current_chat and self.current_chat.startswith('group:'):
            self.messages_text.config(state='normal')
            self.messages_text.insert(tk.END, f"ℹ️ {data['message']} ({data['timestamp']})\n", 'notification')
            self.messages_text.config(state='disabled')
            self.messages_text.see(tk.END)
    
    def clear_messages(self):
        self.messages_text.config(state='normal')
        self.messages_text.delete(1.0, tk.END)
        self.messages_text.config(state='disabled')
    
    def on_typing(self, event):
        if self.current_chat and self.current_chat.startswith('private:'):
            username = self.current_chat.split(':', 1)[1]
            typing_data = {
                'action': 'typing',
                'recipient': username,
                'is_typing': True
            }
            self.send_message(typing_data)
            
            # Stop typing indicator after 3 seconds
            self.root.after(3000, lambda: self.send_message({
                'action': 'typing',
                'recipient': username,
                'is_typing': False
            }))
    
    def update_typing_indicator(self, data):
        if self.current_chat == f"private:{data['sender']}":
            if data['is_typing']:
                self.typing_label.config(text=f"{data['sender']} is typing...")
            else:
                self.typing_label.config(text="")
    
    def update_contact_status(self, data):
        # Refresh contacts list to show updated status
        self.refresh_contacts()
    
    def show_search_results(self, results):
        # This would be called from a search dialog
        pass
    
    # NEW: dialog to add friend to current group
    def add_member_to_group_dialog(self):
        if not self.current_chat or not self.current_chat.startswith('group:'):
            return
        group_id = self.current_chat.split(':', 1)[1]
        friend_username = simpledialog.askstring("Add Member", "Enter friend's username (must be in your contacts):")
        if friend_username:
            self.send_message({
                'action': 'add_friend_to_group',
                'group_id': group_id,
                'friend': friend_username.strip()
            })
    
    def leave_current_group(self):
        if not self.current_chat or not self.current_chat.startswith('group:'):
            return
        gid = self.current_chat.split(':',1)[1]
        if not messagebox.askyesno("Leave Group", "Are you sure you want to leave this group?"):
            return
        self.send_message({'action':'leave_group','group_id':gid})
        # optimistic UI
        self.current_chat = None
        self.chat_title_label.config(text="Select a contact or group to start chatting")
        self.clear_messages()
        self.message_entry.config(state='disabled')
        self.add_member_btn.pack_forget()
        self.leave_group_btn.pack_forget()
        self.refresh_groups()

    def remove_contact_dialog(self):
        """Prompt and remove a contact (friend)."""
        username = simpledialog.askstring("Remove Friend", "Enter friend's username to remove:")
        if not username:
            return
        if not messagebox.askyesno("Confirm", f"Remove '{username}' from your contacts?"):
            return
        self.send_message({'action': 'remove_contact', 'username': username})
        # brief delay before refresh to let server respond
        self.root.after(600, self.refresh_contacts)
    
    def attach_file(self):
        # REPLACED: now supports up to 100MB with chunked protocol
        if not self.current_chat:
            messagebox.showinfo("Info", "Open a chat first.")
            return
        path = filedialog.askopenfilename(title="Select file")
        if not path: return
        size = os.path.getsize(path)
        if size > MAX_FILE_SIZE:
            messagebox.showerror("Error", f"File too large (max {MAX_FILE_SIZE//1024//1024}MB).")
            return
        filename = os.path.basename(path)
        ctype, cid = self.current_chat.split(':',1)
        is_group = (ctype == 'group')
        transfer_id = f"{int(time.time()*1000)}_{filename}"
        start_payload = {
            'action': 'send_group_file_start' if is_group else 'send_file_start',
            'transfer_id': transfer_id,
            'filename': filename,
            'total_size': size
        }
        if is_group:
            start_payload['group_id'] = cid
        else:
            start_payload['recipient'] = cid
        self.send_message(start_payload)
        # send chunks
        try:
            with open(path, 'rb') as f:
                seq = 0
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk: break
                    b64 = base64.b64encode(chunk).decode('utf-8')
                    chunk_payload = {
                        'action': 'send_group_file_chunk' if is_group else 'send_file_chunk',
                        'transfer_id': transfer_id,
                        'seq': seq,
                        'data': b64
                    }
                    if is_group:
                        chunk_payload['group_id'] = cid
                    else:
                        chunk_payload['recipient'] = cid
                    self.send_message(chunk_payload)
                    seq += 1
            end_payload = {
                'action': 'send_group_file_end' if is_group else 'send_file_end',
                'transfer_id': transfer_id
            }
            if is_group:
                end_payload['group_id'] = cid
            else:
                end_payload['recipient'] = cid
            self.send_message(end_payload)
            # local echo
            self.messages_text.config(state='normal')
            self.messages_text.insert(tk.END, f"You ({time.strftime('%H:%M')}): [Sent file: {filename} ({size//1024}KB)]\n", 'own_message')
            self.messages_text.config(state='disabled')
            self.messages_text.see(tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Send failed: {e}")

    # NEW incoming chunked handlers
    def handle_file_start(self, data):
        is_group = data['type'].startswith('group_')
        # Filter by current chat
        if is_group:
            gid = data.get('group_id')
            if self.current_chat != f"group:{gid}":
                # still store to allow later display if user opens chat after complete? Simplify: discard
                return
        else:
            sender = data['sender']
            if self.current_chat != f"private:{sender}":
                return
        tid = data['transfer_id']
        self.incoming_files[tid] = {
            'parts': [],
            'filename': data['filename'],
            'is_group': is_group,
            'sender': data['sender'],
            'total': data.get('total_size', 0),
            'received': 0,
            'timestamp': data.get('timestamp', time.strftime('%H:%M'))
        }

    def handle_file_chunk(self, data):
        tid = data['transfer_id']
        info = self.incoming_files.get(tid)
        if not info: return
        try:
            raw = base64.b64decode(data['data'].encode('utf-8'))
        except:
            return
        info['parts'].append(raw)
        info['received'] += len(raw)

    def handle_file_end(self, data):
        tid = data['transfer_id']
        info = self.incoming_files.pop(tid, None)
        if not info: return
        # Reconstruct
        full = b''.join(info['parts'])
        filename = info['filename']
        sender = info['sender']; ts = info['timestamp']
        # Display save button
        def save_file():
            save_path = filedialog.asksaveasfilename(initialfile=filename, title="Save file")
            if not save_path: return
            try:
                with open(save_path,'wb') as f:
                    f.write(full)
                messagebox.showinfo("Saved","File saved.")
            except Exception as e:
                messagebox.showerror("Error", f"Save failed: {e}")
        self.messages_text.config(state='normal')
        self.messages_text.insert(tk.END, f"{sender} ({ts}): ")
        btn = tk.Button(self.messages_text, text=f"[File: {filename} ({len(full)//1024}KB)]",
                        fg='blue', relief='flat', cursor='hand2', command=save_file)
        self.messages_text.window_create(tk.END, window=btn)
        self.messages_text.insert(tk.END, "\n")
        self.messages_text.config(state='disabled')
        self.messages_text.see(tk.END)
    
    def run(self):
        try:
            self.root.mainloop()
        finally:
            if self.connected:
                self.client.close()


class ProfileDialog:
    def __init__(self, parent, current_avatar, current_nickname, current_username):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Profile")
        self.dialog.geometry("300x250")
        self.dialog.configure(bg='#2c3e50')
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        # Avatar selection
        tk.Label(self.dialog, text="Avatar:", font=('Arial', 12), bg='#2c3e50', fg='white').pack(pady=10)
        
        self.avatar_var = tk.StringVar(value=current_avatar)
        avatar_frame = tk.Frame(self.dialog, bg='#2c3e50')
        avatar_frame.pack()
        
        avatars = ['👤', '😀', '😎', '🤖', '👨', '👩', '🧑', '👶']
        for i, avatar in enumerate(avatars):
            rb = tk.Radiobutton(avatar_frame, text=avatar, variable=self.avatar_var, 
                               value=avatar, bg='#2c3e50', fg='white', font=('Arial', 16),
                               selectcolor='#34495e')
            rb.grid(row=i//4, column=i%4, padx=5, pady=5)
        
        # Nickname entry
        tk.Label(self.dialog, text="Nickname:", font=('Arial', 12), bg='#2c3e50', fg='white').pack(pady=(20, 5))
        
        self.nickname_entry = tk.Entry(self.dialog, font=('Arial', 12))
        self.nickname_entry.pack(pady=5)
        self.nickname_entry.insert(0, current_nickname)
        
        # Username edit
        tk.Label(self.dialog, text="Username:", font=('Arial', 12), bg='#2c3e50', fg='white').pack(pady=(10,5))
        self.username_entry = tk.Entry(self.dialog, font=('Arial',12))
        self.username_entry.pack()
        self.username_entry.insert(0, current_username)
        
        # Buttons
        button_frame = tk.Frame(self.dialog, bg='#2c3e50')
        button_frame.pack(pady=20)
        
        tk.Button(button_frame, text="Save", command=self.save, 
                 bg='#27ae60', fg='white', font=('Arial', 12), relief='flat').pack(side='left', padx=10)
        tk.Button(button_frame, text="Cancel", command=self.cancel, 
                 bg='#e74c3c', fg='white', font=('Arial', 12), relief='flat').pack(side='left', padx=10)
        
        self.nickname_entry.focus()
        self.dialog.bind('<Return>', lambda e: self.save())
    
    def save(self):
        nickname = self.nickname_entry.get().strip()
        username = self.username_entry.get().strip()
        if nickname and username:
            self.result = (self.avatar_var.get(), nickname, username)
            self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


if __name__ == "__main__":
    client = ChatClient()
    client.run()