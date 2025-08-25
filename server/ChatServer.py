import socket
import threading
import json
import time
from datetime import datetime
import base64  # --- added

MAX_FILE_SIZE = 100 * 1024 * 1024    # 100MB

class ChatServer:
    def __init__(self, host='0.0.0.0', port=12345):
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

    def register_user(self, client, data):
        username = data.get('username')
        
        if username in self.users:
            response = {'success': False, 'message': 'Username already exists'}
        else:
            self.users[username] = {
                'profile': {
                    'nickname': username,
                    'avatar': '👤',
                    'status': 'online'
                },
                'contacts': [],
                'status': 'online'
            }
            response = {'success': True, 'message': 'Registration successful'}
        
        self.send_json(client, response)
    
    def login_user(self, client, data):
        username = data.get('username')
        
        if username not in self.users:
            response = {'success': False, 'message': 'User not found'}
        else:
            self.clients[client] = {'username': username, 'profile': self.users[username]['profile']}
            self.users[username]['status'] = 'online'
            response = {'success': True, 'message': 'Login successful', 'profile': self.users[username]['profile']}
            
            # Notify contacts that user is online
            self.notify_status_change(username, 'online')
        
        self.send_json(client, response)
    
    def update_profile(self, client, data):
        if client in self.clients:
            username = self.clients[client]['username']
            profile_updates = data.get('profile', {})
            
            self.users[username]['profile'].update(profile_updates)
            self.clients[client]['profile'].update(profile_updates)
            response = {'success': True, 'message': 'Profile updated'}
            # NEW: broadcast profile update (avatar / nickname) to contacts & group members
            self.broadcast_profile_update(username)
        else:
            response = {'success': False, 'message': 'Not logged in'}
        
        self.send_json(client, response)
    
    def search_users(self, client, data):
        query = data.get('query', '').lower()
        results = []
        
        for username, user_data in self.users.items():
            if query in username.lower() or query in user_data['profile']['nickname'].lower():
                results.append({
                    'username': username,
                    'nickname': user_data['profile']['nickname'],
                    'avatar': user_data['profile']['avatar'],
                    'status': user_data['status']
                })
        
        response = {'results': results}
        self.send_json(client, response)
    
    def add_contact(self, client, data):
        if client in self.clients:
            username = self.clients[client]['username']
            contact_username = data.get('username')
            
            if contact_username in self.users and contact_username not in self.users[username]['contacts']:
                self.users[username]['contacts'].append(contact_username)
                response = {'success': True, 'message': f'Added {contact_username} to contacts'}
            else:
                response = {'success': False, 'message': 'User not found or already in contacts'}
        else:
            response = {'success': False, 'message': 'Not logged in'}
        
        self.send_json(client, response)
    
    def remove_contact(self, client, data):
        if client in self.clients:
            username = self.clients[client]['username']
            contact_username = data.get('username')
            
            if contact_username in self.users[username]['contacts']:
                self.users[username]['contacts'].remove(contact_username)
                response = {'success': True, 'message': f'Removed {contact_username} from contacts'}
            else:
                response = {'success': False, 'message': 'Contact not found'}
        else:
            response = {'success': False, 'message': 'Not logged in'}
        
        self.send_json(client, response)
    
    def get_contacts(self, client):
        if client in self.clients:
            username = self.clients[client]['username']
            contacts = []
            
            for contact_username in self.users[username]['contacts']:
                if contact_username in self.users:
                    contacts.append({
                        'username': contact_username,
                        'nickname': self.users[contact_username]['profile']['nickname'],
                        'avatar': self.users[contact_username]['profile']['avatar'],
                        'status': self.users[contact_username]['status']
                    })
            
            response = {'contacts': contacts}
        else:
            response = {'contacts': []}
        
        self.send_json(client, response)
    
    def send_private_message(self, client, data):
        if client in self.clients:
            sender = self.clients[client]['username']
            recipient = data.get('recipient')
            message = data.get('message')
            
            # Find recipient's client
            recipient_client = None
            for cli, client_data in self.clients.items():
                if client_data['username'] == recipient:
                    recipient_client = cli
                    break
            
            if recipient_client:
                message_data = {
                    'type': 'private_message',
                    'sender': sender,
                    'message': message,
                    'timestamp': datetime.now().strftime('%H:%M'),
                    'avatar': self.users[sender]['profile']['avatar']
                }
                self.send_json(recipient_client, message_data)   # CHANGED (framed)
                response = {'success': True, 'message': 'Message sent'}
            else:
                response = {'success': False, 'message': 'Recipient not online'}
        else:
            response = {'success': False, 'message': 'Not logged in'}
        self.send_json(client, response)
    
    def create_group(self, client, data):
        if client in self.clients:
            username = self.clients[client]['username']
            group_name = data.get('group_name')
            group_id = f"group_{len(self.groups) + 1}"
            
            self.groups[group_id] = {
                'name': group_name,
                'members': [username],
                'messages': [],
                'admin': username
            }
            
            response = {'success': True, 'message': f'Group "{group_name}" created', 'group_id': group_id}
        else:
            response = {'success': False, 'message': 'Not logged in'}
        
        self.send_json(client, response)
    
    def join_group(self, client, data):
        if client in self.clients:
            username = self.clients[client]['username']
            group_id = data.get('group_id')
            
            if group_id in self.groups and username not in self.groups[group_id]['members']:
                self.groups[group_id]['members'].append(username)
                response = {'success': True, 'message': f'Joined group "{self.groups[group_id]["name"]}"'}
                
                # Notify other group members
                self.notify_group_members(group_id, {
                    'type': 'group_notification',
                    'message': f'{username} joined the group',
                    'timestamp': datetime.now().strftime('%H:%M')
                }, exclude=username)
            else:
                response = {'success': False, 'message': 'Group not found or already a member'}
        else:
            response = {'success': False, 'message': 'Not logged in'}
        
        self.send_json(client, response)
    
    def leave_group(self, client, data):
        if client in self.clients:
            username = self.clients[client]['username']
            group_id = data.get('group_id')
            
            if group_id in self.groups and username in self.groups[group_id]['members']:
                self.groups[group_id]['members'].remove(username)
                response = {'success': True, 'message': f'Left group "{self.groups[group_id]["name"]}"'}
                
                # Notify other group members
                self.notify_group_members(group_id, {
                    'type': 'group_notification',
                    'message': f'{username} left the group',
                    'timestamp': datetime.now().strftime('%H:%M')
                })
            else:
                response = {'success': False, 'message': 'Group not found or not a member'}
        else:
            response = {'success': False, 'message': 'Not logged in'}
        
        self.send_json(client, response)
    
    def send_group_message(self, client, data):
        if client in self.clients:
            username = self.clients[client]['username']
            group_id = data.get('group_id')
            message = data.get('message')
            
            if group_id in self.groups and username in self.groups[group_id]['members']:
                message_data = {
                    'type': 'group_message',
                    'group_id': group_id,
                    'group_name': self.groups[group_id]['name'],
                    'sender': username,
                    'message': message,
                    'timestamp': datetime.now().strftime('%H:%M'),
                    'avatar': self.users[username]['profile']['avatar']
                }
                
                self.notify_group_members(group_id, message_data, exclude=username)
                response = {'success': True, 'message': 'Message sent to group'}
            else:
                response = {'success': False, 'message': 'Group not found or not a member'}
        else:
            response = {'success': False, 'message': 'Not logged in'}
        
        self.send_json(client, response)
    
    def get_user_groups(self, client):
        if client in self.clients:
            username = self.clients[client]['username']
            user_groups = []
            
            for group_id, group_data in self.groups.items():
                if username in group_data['members']:
                    user_groups.append({
                        'group_id': group_id,
                        'name': group_data['name'],
                        'member_count': len(group_data['members'])
                    })
            
            response = {'groups': user_groups}
        else:
            response = {'groups': []}
        
        self.send_json(client, response)
    
    def handle_typing(self, client, data):
        if client in self.clients:
            username = self.clients[client]['username']
            recipient = data.get('recipient')
            is_typing = data.get('is_typing', False)
            for cli, client_data in self.clients.items():
                if client_data['username'] == recipient:
                    typing_data = {
                        'type': 'typing_indicator',
                        'sender': username,
                        'is_typing': is_typing
                    }
                    self.send_json(cli, typing_data)  # CHANGED
                    break
    
    def update_status(self, client, data):
        if client in self.clients:
            username = self.clients[client]['username']
            status = data.get('status')
            
            self.users[username]['status'] = status
            self.notify_status_change(username, status)
            
            response = {'success': True, 'message': 'Status updated'}
        else:
            response = {'success': False, 'message': 'Not logged in'}
        
        self.send_json(client, response)
    
    def add_friend_to_group(self, client, data):
        if client not in self.clients:
            self.send_json(client, {'success': False, 'message': 'Not logged in'}); return
        username = self.clients[client]['username']
        group_id = data.get('group_id')
        friend = data.get('friend')
        if not group_id or not friend:
            self.send_json(client, {'success': False, 'message': 'Missing group_id or friend'}); return
        if group_id not in self.groups:
            self.send_json(client, {'success': False, 'message': 'Group not found'}); return
        group = self.groups[group_id]
        if username not in group['members']:
            self.send_json(client, {'success': False, 'message': 'You are not a member of this group'}); return
        if friend not in self.users:
            self.send_json(client, {'success': False, 'message': 'Friend user not found'}); return
        if friend not in self.users[username]['contacts']:
            self.send_json(client, {'success': False, 'message': 'User is not in your contacts'}); return
        if friend in group['members']:
            self.send_json(client, {'success': False, 'message': 'User already in group'}); return
        group['members'].append(friend)
        self.notify_group_members(group_id, {
            'type': 'group_notification',
            'message': f'{friend} was added to the group by {username}',
            'timestamp': datetime.now().strftime('%H:%M')
        })
        added_client = None
        for cli, cd in self.clients.items():
            if cd['username'] == friend:
                added_client = cli; break
        if added_client:
            self.send_json(added_client, {
                'type': 'group_added',
                'group_id': group_id,
                'name': group['name'],
                'member_count': len(group['members'])
            })
        self.send_json(client, {'success': True, 'message': f'Added {friend} to group "{group["name"]}"', 'action': 'add_friend_to_group'})
    
    def broadcast_profile_update(self, username):
        prof = self.users[username]['profile']
        payload = {
            'type': 'profile_update',
            'username': username,
            'nickname': prof['nickname'],
            'avatar': prof['avatar'],
            'status': self.users[username]['status']
        }
        targets = set()
        # contacts who have this user
        for u, ud in self.users.items():
            if username in ud['contacts']:
                targets.add(u)
        # group members
        for g in self.groups.values():
            if username in g['members']:
                for m in g['members']:
                    targets.add(m)
        for cli, cdata in self.clients.items():
            if cdata['username'] in targets:
                self.send_json(cli, payload)

    # --- NEW: change username action ---
    def change_username(self, client, data):
        if client not in self.clients:
            self.send_json(client, {'success': False, 'message': 'Not logged in'}); return
        old = self.clients[client]['username']
        new = data.get('new_username', '').strip()
        if not new:
            self.send_json(client, {'success': False, 'message': 'New username required'}); return
        if new in self.users:
            self.send_json(client, {'success': False, 'message': 'Username already taken'}); return
        # migrate user record
        self.users[new] = self.users.pop(old)
        # update contacts lists
        for u, ud in self.users.items():
            if old in ud['contacts']:
                ud['contacts'] = [new if c == old else c for c in ud['contacts']]
        # update groups
        for gid, g in self.groups.items():
            if old in g['members']:
                g['members'] = [new if m == old else m for m in g['members']]
                if g.get('admin') == old:
                    g['admin'] = new
        # update client mapping
        self.clients[client]['username'] = new
        # notify contacts & group members
        notice = {
            'type': 'username_changed',
            'old_username': old,
            'new_username': new
        }
        targets = set()
        for u, ud in self.users.items():
            if (old in ud['contacts']) or (new in ud['contacts']):
                targets.add(u)
        for g in self.groups.values():
            if new in g['members']:
                for m in g['members']:
                    targets.add(m)
        for cli, cd in self.clients.items():
            if cd['username'] in targets and cli != client:
                self.send_json(cli, notice)
        self.send_json(client, {'success': True,
                                'message': 'Username changed',
                                'profile': self.users[new]['profile'],
                                'new_username': new})
        # also broadcast profile (with new username context)
        self.broadcast_profile_update(new)

    def notify_status_change(self, username, status):
        # Notify all contacts about status change
        for cli, client_data in self.clients.items():
            other_username = client_data['username']
            if username in self.users[other_username]['contacts']:
                status_data = {'type': 'status_update','username': username,'status': status}
                self.send_json(cli, status_data)  # CHANGED
    
    def notify_group_members(self, group_id, message_data, exclude=None):
        if group_id in self.groups:
            for member in self.groups[group_id]['members']:
                if member != exclude:
                    for cli, client_data in self.clients.items():
                        if client_data['username'] == member:
                            self.send_json(cli, message_data)  # CHANGED
                            break
    
    def disconnect_client(self, client):
        if client in self.clients:
            username = self.clients[client]['username']
            self.users[username]['status'] = 'offline'
            self.notify_status_change(username, 'offline')
            del self.clients[client]
        
        client.close()

    # --- NEW (test server): private file send ---
    def send_file(self, client, data):
        if client not in self.clients:
            self.send_json(client, {'success': False, 'message': 'Not logged in'}); return
        sender = self.clients[client]['username']
        recipient = data.get('recipient')
        filename = data.get('filename')
        b64 = data.get('data')
        if not all([recipient, filename, b64]):
            self.send_json(client, {'success': False, 'message': 'Missing file data'}); return
        try:
            raw = base64.b64decode(b64.encode('utf-8'))
        except:
            self.send_json(client, {'success': False, 'message': 'Corrupted file data'}); return
        if len(raw) > 200*1024:
            self.send_json(client, {'success': False, 'message': 'File too large (max 200KB)'}); return
        target = None
        for cli, cd in self.clients.items():
            if cd['username'] == recipient:
                target = cli
                break
        if not target:
            self.send_json(client, {'success': False, 'message': 'Recipient not online'}); return
        msg = {
            'type': 'file_message',
            'sender': sender,
            'filename': filename,
            'data': b64,
            'timestamp': datetime.now().strftime('%H:%M'),
            'avatar': self.users[sender]['profile']['avatar']
        }
        self.send_json(target, msg)
        self.send_json(client, {'success': True, 'message': 'File sent'})  # CHANGED

    # --- NEW (test server): group file send ---
    def send_group_file(self, client, data):
        if client not in self.clients:
            self.send_json(client, {'success': False, 'message': 'Not logged in'}); return
        sender = self.clients[client]['username']
        gid = data.get('group_id')
        filename = data.get('filename')
        b64 = data.get('data')
        if not all([gid, filename, b64]):
            self.send_json(client, {'success': False, 'message': 'Missing file data'}); return
        if gid not in self.groups or sender not in self.groups[gid]['members']:
            self.send_json(client, {'success': False, 'message': 'Not in group'}); return
        try:
            raw = base64.b64decode(b64.encode('utf-8'))
        except:
            self.send_json(client, {'success': False, 'message': 'Corrupted file data'}); return
        if len(raw) > 200*1024:
            self.send_json(client, {'success': False, 'message': 'File too large (max 200KB)'}); return
        payload = {
            'type': 'group_file_message',
            'group_id': gid,
            'group_name': self.groups[gid]['name'],
            'sender': sender,
            'filename': filename,
            'data': b64,
            'timestamp': datetime.now().strftime('%H:%M'),
            'avatar': self.users[sender]['profile']['avatar']
        }
        for member in self.groups[gid]['members']:
            if member == sender: continue
            for cli, cd in self.clients.items():
                if cd['username'] == member:
                    self.send_json(cli, payload)  # CHANGED
                    break
        self.send_json(client, {'success': True, 'message': 'File sent to group'})  # CHANGED

    # --- NEW chunked private file forwarding (stateless) ---
    def send_file_start(self, client, data):
        if client not in self.clients:
            self.send_json(client, {'success': False, 'message': 'Not logged in'}); return
        sender = self.clients[client]['username']
        recipient = data.get('recipient'); filename = data.get('filename'); total = data.get('total_size', 0)
        if not recipient or not filename:
            self.send_json(client, {'success': False, 'message': 'Missing fields'}); return
        if total > MAX_FILE_SIZE:
            self.send_json(client, {'success': False, 'message': 'File too large'}); return
        target = self._find_client(recipient)
        if not target:
            self.send_json(client, {'success': False, 'message': 'Recipient not online'}); return
        payload = {
            'type': 'file_start',
            'transfer_id': data['transfer_id'],
            'filename': filename,
            'total_size': total,
            'sender': sender,
            'timestamp': datetime.now().strftime('%H:%M')
        }
        self.send_json(target, payload)

    def send_file_chunk(self, client, data):
        if client not in self.clients: return
        sender = self.clients[client]['username']
        recipient = data.get('recipient')
        target = self._find_client(recipient)
        if not target: return
        payload = {
            'type': 'file_chunk',
            'transfer_id': data['transfer_id'],
            'seq': data.get('seq', 0),
            'data': data.get('data',''),
            'sender': sender
        }
        self.send_json(target, payload)

    def send_file_end(self, client, data):
        if client not in self.clients: return
        sender = self.clients[client]['username']
        recipient = data.get('recipient')
        target = self._find_client(recipient)
        if not target: return
        payload = {
            'type': 'file_end',
            'transfer_id': data['transfer_id'],
            'sender': sender
        }
        self.send_json(target, payload)

    # --- NEW chunked group file forwarding ---
    def send_group_file_start(self, client, data):
        if client not in self.clients:
            self.send_json(client, {'success': False, 'message': 'Not logged in'}); return
        sender = self.clients[client]['username']
        gid = data.get('group_id'); filename = data.get('filename'); total = data.get('total_size',0)
        if not gid or gid not in self.groups or sender not in self.groups[gid]['members']:
            self.send_json(client, {'success': False, 'message': 'Not in group'}); return
        if total > MAX_FILE_SIZE:
            self.send_json(client, {'success': False, 'message': 'File too large'}); return
        payload = {
            'type': 'group_file_start',
            'transfer_id': data['transfer_id'],
            'group_id': gid,
            'filename': filename,
            'total_size': total,
            'sender': sender,
            'timestamp': datetime.now().strftime('%H:%M')
        }
        self._broadcast_group(gid, sender, payload)

    def send_group_file_chunk(self, client, data):
        if client not in self.clients: return
        sender = self.clients[client]['username']
        gid = data.get('group_id')
        if not gid or gid not in self.groups or sender not in self.groups[gid]['members']:
            return
        payload = {
            'type': 'group_file_chunk',
            'transfer_id': data['transfer_id'],
            'group_id': gid,
            'seq': data.get('seq',0),
            'data': data.get('data',''),
            'sender': sender
        }
        self._broadcast_group(gid, sender, payload)

    def send_group_file_end(self, client, data):
        if client not in self.clients: return
        sender = self.clients[client]['username']
        gid = data.get('group_id')
        if not gid or gid not in self.groups or sender not in self.groups[gid]['members']:
            return
        payload = {
            'type': 'group_file_end',
            'transfer_id': data['transfer_id'],
            'group_id': gid,
            'sender': sender
        }
        self._broadcast_group(gid, sender, payload)

    # --- helpers ---
    def _find_client(self, username):
        for cli, cd in self.clients.items():
            if cd['username'] == username:
                return cli
        return None

    def _broadcast_group(self, group_id, sender, payload):
        for member in self.groups.get(group_id, {}).get('members', []):
            if member == sender: continue
            cli = self._find_client(member)
            if cli:
                self.send_json(cli, payload)

# --- ADDED main entry point (was missing) ---
if __name__ == "__main__":
    server = ChatServer()
    try:
        server.start_server()
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        server.running = False