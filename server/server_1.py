import socket
import threading
import json
import time
from datetime import datetime
import base64  # --- added

MAX_FILE_SIZE = 100 * 1024 * 1024    # 100MB

class ChatServer:
    def __init__(self, host='localhost', port=12345):
        self.host = host
        self.port = port
        self.clients = {}  # {socket: {'username': str, 'profile': dict}}
        self.users = {}    # {username: {'profile': dict, 'contacts': list, 'status': str}}
        self.groups = {}   # {group_id: {'name': str, 'members': list, 'messages': list}}
        self.running = True
        
    def start_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen()
        
        print(f"Server listening on {self.host}:{self.port}")
        
        while self.running:
            try:
                client, address = server.accept()
                print(f"Connected with {str(address)}")
                
                thread = threading.Thread(target=self.handle_client, args=(client,))
                thread.start()
            except:
                break
                
        server.close()
    
    def send_json(self, client, obj):
        try:
            client.send((json.dumps(obj) + "\n").encode('utf-8'))
        except:
            pass

    def handle_client(self, client):
        buffer = ""
        while True:
            try:
                chunk = client.recv(4096).decode('utf-8')
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
                    self.process_message(client, data)
            except:
                break
        self.disconnect_client(client)
    
    def process_message(self, client, data):
        action = data.get('action')
        
        if action == 'register':
            self.register_user(client, data)
        elif action == 'login':
            self.login_user(client, data)
        elif action == 'update_profile':
            self.update_profile(client, data)
        elif action == 'search_users':
            self.search_users(client, data)
        elif action == 'add_contact':
            self.add_contact(client, data)
        elif action == 'remove_contact':
            self.remove_contact(client, data)
        elif action == 'get_contacts':
            self.get_contacts(client)
        elif action == 'send_message':
            self.send_private_message(client, data)
        elif action == 'create_group':
            self.create_group(client, data)
        elif action == 'join_group':
            self.join_group(client, data)
        elif action == 'leave_group':
            self.leave_group(client, data)
        elif action == 'send_group_message':
            self.send_group_message(client, data)
        elif action == 'get_groups':
            self.get_user_groups(client)
        elif action == 'typing':
            self.handle_typing(client, data)
        elif action == 'update_status':
            self.update_status(client, data)
        elif action == 'add_friend_to_group':
            self.add_friend_to_group(client, data)
        elif action == 'change_username':
            self.change_username(client, data)
        elif action == 'send_file':
            self.send_file(client, data)          # --- added
        elif action == 'send_group_file':
            self.send_group_file(client, data)
        # --- NEW chunked actions ---
        elif action == 'send_file_start':
            self.send_file_start(client, data)
        elif action == 'send_file_chunk':
            self.send_file_chunk(client, data)
        elif action == 'send_file_end':
            self.send_file_end(client, data)
        elif action == 'send_group_file_start':
            self.send_group_file_start(client, data)
        elif action == 'send_group_file_chunk':
            self.send_group_file_chunk(client, data)
        elif action == 'send_group_file_end':
            self.send_group_file_end(client, data)