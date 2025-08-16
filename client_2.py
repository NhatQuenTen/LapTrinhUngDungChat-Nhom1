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
    
    # --- NEW handlers for profile & username events ---
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
