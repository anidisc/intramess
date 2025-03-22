import socket
import threading
import json
import logging
from datetime import datetime
from colorama import init, Fore, Style

# Inizializzazione colorama per i colori nel terminale
init()

# Configurazione del logging
logging.basicConfig(
    filename='server.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Server:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.clients = {}  # {client_socket: username}
        self.groups = {'ALL': set()}  # {group_name: set(usernames)}
        self.user_groups = {}  # {username: group_name}
        self.running = True
        self.commands = {
            'help': ('Mostra questo messaggio di aiuto', self.show_help),
            'list': ('Mostra la lista degli utenti connessi', self.list_users),
            'broadcast': ('Invia un messaggio a tutti gli utenti (uso: broadcast <messaggio>)', self.server_broadcast),
            'kick': ('Disconnette un utente (uso: kick <username>)', self.kick_user),
            'log': ('Mostra gli ultimi 10 log del server', self.show_logs),
            'stop': ('Arresta il server', self.stop_server),
            'creategroup': ('Crea un nuovo gruppo (uso: creategroup <nome_gruppo>)', self.create_group),
            'listgroups': ('Mostra tutti i gruppi disponibili', self.list_groups),
            'deletegroup': ('Elimina un gruppo (uso: deletegroup <nome_gruppo>)', self.delete_group),
        }
        logging.info(f"Server avviato su {host}:{port}")
        logging.info("Server avviato con gruppo predefinito 'ALL'")

    def show_help(self, *args):
        """Mostra l'elenco dei comandi disponibili"""
        print(f"{Fore.YELLOW}Comandi disponibili:{Style.RESET_ALL}")
        for cmd, (desc, _) in self.commands.items():
            print(f"- {Fore.CYAN}{cmd}{Style.RESET_ALL}: {desc}")

    def list_users(self, *args):
        """Mostra la lista degli utenti connessi"""
        print(f"{Fore.YELLOW}Client connessi:{Style.RESET_ALL}")
        for username in self.clients.values():
            print(f"- {username}")

    def server_broadcast(self, *args):
        """Invia un messaggio broadcast a tutti i client"""
        if not args or not args[0]:
            print(f"{Fore.RED}Errore: Specificare un messaggio da inviare{Style.RESET_ALL}")
            return
        
        # Converti args in una stringa
        message = ' '.join(str(arg) for arg in args)
        for client in self.clients:
            try:
                client.send(json.dumps({
                    'type': 'system',
                    'message': f"[Server Broadcast] {message}"
                }).encode())
            except:
                self.remove_client(client)
        
        logging.info(f"Server broadcast: {message}")
        print(f"{Fore.GREEN}Messaggio broadcast inviato{Style.RESET_ALL}")

    def kick_user(self, *args):
        """Disconnette un utente specificato"""
        if not args or not args[0]:
            print(f"{Fore.RED}Errore: Specificare un username{Style.RESET_ALL}")
            return
        
        username = args[0]
        for client, name in self.clients.items():
            if name == username:
                self.remove_client(client)
                print(f"{Fore.GREEN}Utente {username} disconnesso{Style.RESET_ALL}")
                return
        
        print(f"{Fore.RED}Utente {username} non trovato{Style.RESET_ALL}")

    def show_logs(self, *args):
        """Mostra gli ultimi log del server"""
        try:
            with open('server.log', 'r') as f:
                print(f"{Fore.YELLOW}Ultimi log:{Style.RESET_ALL}")
                for line in f.readlines()[-10:]:
                    print(line.strip())
        except:
            print(f"{Fore.RED}Errore nella lettura del file di log{Style.RESET_ALL}")

    def stop_server(self, *args):
        """Arresta il server"""
        try:
            # Invia messaggio di disconnessione a tutti i client
            for client in list(self.clients.keys()):
                try:
                    client.send(json.dumps({
                        'type': 'server_shutdown',
                        'message': 'Il server sta per essere arrestato'
                    }).encode())
                    client.close()
                except:
                    pass
            
            # Chiudi il socket del server
            self.server_socket.close()
            
            # Pulisci la lista dei client
            self.clients.clear()
            
            # Imposta il flag di arresto
            self.running = False
            
            print(f"{Fore.RED}Server arrestato correttamente{Style.RESET_ALL}")
            logging.info("Server arrestato")
            
            # Termina il processo
            import os, signal
            os.kill(os.getpid(), signal.SIGTERM)
            
        except Exception as e:
            logging.error(f"Errore durante l'arresto del server: {str(e)}")
        
        return True

    def is_username_taken(self, username):
        """Verifica se l'username è già in uso"""
        return username in self.clients.values()

    def broadcast_user_list(self):
        """Invia la lista degli utenti connessi con i loro gruppi"""
        users_data = {}
        for client_socket, username in self.clients.items():
            users_data[username] = {
                'group': self.user_groups.get(username, 'ALL')
            }
        
        print(f"DEBUG: Invio lista utenti: {users_data}")  # Debug
        
        message = json.dumps({
            'type': 'user_list',
            'users': users_data
        }) + '\n'
        
        for client_socket in self.clients:
            try:
                client_socket.send(message.encode())
            except:
                self.remove_client(client_socket)

    def broadcast(self, message, sender=None):
        """Invia un messaggio a tutti i client connessi"""
        for client in self.clients:
            if client != sender:
                try:
                    client.send(json.dumps(message).encode())
                except:
                    self.remove_client(client)

    def send_private_message(self, sender, recipient, message):
        """Invia un messaggio privato a un utente specifico"""
        recipient_socket = None
        for client, username in self.clients.items():
            if username == recipient:
                recipient_socket = client
                break

        if recipient_socket:
            try:
                private_message = {
                    'type': 'private',
                    'from': self.clients[sender],
                    'message': message
                }
                recipient_socket.send(json.dumps(private_message).encode())
                sender.send(json.dumps({
                    'type': 'system',
                    'message': f"Messaggio inviato a {recipient}"
                }).encode())
            except:
                self.remove_client(recipient_socket)
        else:
            sender.send(json.dumps({
                'type': 'error',
                'message': f"Utente {recipient} non trovato"
            }).encode())

    def create_group(self, args):
        """Crea un nuovo gruppo"""
        if not args or not args[0]:
            print(f"{Fore.RED}Errore: Specificare un nome per il gruppo{Style.RESET_ALL}")
            return False
        
        group_name = args[0].upper()
        if group_name == 'ALL':
            print(f"{Fore.RED}Errore: Il nome 'ALL' è riservato{Style.RESET_ALL}")
            return False
            
        if group_name in self.groups:
            print(f"{Fore.RED}Errore: Il gruppo {group_name} esiste già{Style.RESET_ALL}")
            return False
            
        self.groups[group_name] = set()
        print(f"{Fore.GREEN}Gruppo {group_name} creato con successo{Style.RESET_ALL}")
        logging.info(f"Nuovo gruppo creato: {group_name}")
        
        # Notifica tutti i client del nuovo gruppo
        self.broadcast({
            'type': 'groups_list',
            'groups': list(self.groups.keys())
        })
        return False  # Non terminare il server

    def delete_group(self, *args):
        """Elimina un gruppo"""
        if not args or not args[0]:
            print(f"{Fore.RED}Errore: Specificare il nome del gruppo{Style.RESET_ALL}")
            return
            
        group_name = args[0].upper()
        if group_name == 'ALL':
            print(f"{Fore.RED}Errore: Il gruppo 'ALL' non può essere eliminato{Style.RESET_ALL}")
            return
            
        if group_name not in self.groups:
            print(f"{Fore.RED}Errore: Il gruppo {group_name} non esiste{Style.RESET_ALL}")
            return
            
        # Sposta gli utenti del gruppo eliminato nel gruppo ALL
        for username in self.groups[group_name]:
            self.groups['ALL'].add(username)
            self.user_groups[username] = 'ALL'
            
        del self.groups[group_name]
        print(f"{Fore.GREEN}Gruppo {group_name} eliminato{Style.RESET_ALL}")
        logging.info(f"Gruppo eliminato: {group_name}")
        
        # Notifica tutti i client
        self.broadcast_groups()

    def list_groups(self, *args):
        """Mostra la lista dei gruppi"""
        print(f"{Fore.YELLOW}Gruppi disponibili:{Style.RESET_ALL}")
        for group, members in self.groups.items():
            print(f"- {group}: {len(members)} utenti")
            for member in members:
                print(f"  • {member}")

    def broadcast_groups(self):
        """Invia la lista dei gruppi a tutti i client"""
        for client in self.clients:
            try:
                client.send(json.dumps({
                    'type': 'groups_list',
                    'groups': list(self.groups.keys())
                }).encode())
            except:
                self.remove_client(client)

    def handle_client(self, client_socket):
        try:
            username = client_socket.recv(1024).decode()
            if username in [u for u in self.clients.values()]:
                client_socket.send((json.dumps({
                    'type': 'error',
                    'message': 'Username già in uso'
                }) + '\n').encode())
                return
            
            # Registra il client
            self.clients[client_socket] = username
            self.groups['ALL'].add(username)
            self.user_groups[username] = 'ALL'

            # Invia conferma e lista gruppi disponibili
            client_socket.send((json.dumps({
                'type': 'connection_accepted',
                'groups': list(self.groups.keys())
            }) + '\n').encode())

            # Notifica tutti della nuova connessione
            self.broadcast_to_group({
                'type': 'system',
                'message': f'{username} si è unito alla chat'
            })

            # Invia lista utenti a tutti
            self.broadcast_user_list()

            while self.running:
                try:
                    message = client_socket.recv(1024).decode()
                    if not message:
                        break

                    messages = message.split('\n')
                    for msg in messages:
                        if not msg:
                            continue
                            
                        data = json.loads(msg)
                        print(f"DEBUG: Ricevuto da {username}: {data}")

                        if data['type'] == 'request_users':
                            client_socket.send((json.dumps({
                                'type': 'user_list',
                                'users': list(self.clients.values())
                            }) + '\n').encode())
                        
                        elif data['type'] == 'private_message':
                            target = data['to']
                            if target in self.clients.values():
                                # Trova il socket del destinatario
                                target_socket = next(
                                    (s for s, u in self.clients.items() if u == target),
                                    None
                                )
                                if target_socket:
                                    # Invia al destinatario
                                    target_socket.send((json.dumps({
                                        'type': 'private',
                                        'from': username,
                                        'message': data['message']
                                    }) + '\n').encode())
                                    # Conferma al mittente
                                    client_socket.send((json.dumps({
                                        'type': 'private',
                                        'to': target,
                                        'message': data['message']
                                    }) + '\n').encode())
                            else:
                                client_socket.send((json.dumps({
                                    'type': 'error',
                                    'message': f'Utente {target} non trovato'
                                }) + '\n').encode())
                        elif data['type'] == 'group_message':
                            group = data['group'].upper()
                            if group in self.groups:
                                # Verifica che l'utente sia nel gruppo da cui sta inviando
                                if group != 'ALL' and username not in self.groups[group]:
                                    client_socket.send((json.dumps({
                                        'type': 'error',
                                        'message': f'Non sei membro del gruppo {group}'
                                    }) + '\n').encode())
                                    continue

                                self.broadcast_to_group({
                                    'type': 'message',
                                    'from': username,
                                    'message': data['message'],
                                    'group': group
                                }, group=group)
                        elif data['type'] == 'join_group':
                            group = data['group'].upper()
                            if group in self.groups:
                                old_group = self.user_groups[username]
                                if old_group != 'ALL':
                                    self.groups[old_group].remove(username)
                                self.groups[group].add(username)
                                self.user_groups[username] = group
                                
                                # Notifica il cambio gruppo
                                client_socket.send((json.dumps({
                                    'type': 'system',
                                    'message': f'Sei entrato nel gruppo {group}'
                                }) + '\n').encode())
                                
                                # Notifica gli altri utenti
                                self.broadcast_to_group({
                                    'type': 'system',
                                    'message': f'{username} è entrato nel gruppo {group}'
                                }, group=group)
                                
                                # Aggiorna la lista utenti per tutti
                                self.broadcast_user_list()
                                
                                print(f"DEBUG: Utente {username} entrato nel gruppo {group}")

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"DEBUG: Errore gestione client {username}: {e}")
                    break

        finally:
            self.remove_client(client_socket)
            self.broadcast_user_list()

    def broadcast_to_group(self, message, group='ALL', exclude=None):
        print(f"DEBUG: Broadcasting to group {group}: {message}")
        
        # Determina i destinatari in base al gruppo
        recipients = set()
        if group == 'ALL':
            # Se il messaggio è per ALL, lo ricevono tutti
            recipients = set(self.clients.values())
        else:
            # Se il messaggio è per un gruppo specifico, lo ricevono SOLO i membri di quel gruppo
            recipients = self.groups[group]

        for client_socket, username in self.clients.items():
            if username in recipients and (not exclude or username != exclude):
                try:
                    print(f"DEBUG: Invio a {username} nel gruppo {group}")
                    client_socket.send((json.dumps(message) + '\n').encode())
                    print(f"DEBUG: Inviato con successo a {username}")
                except Exception as e:
                    print(f"DEBUG: Errore invio a {username}: {e}")
                    self.remove_client(client_socket)

    def remove_client(self, client_socket):
        if client_socket in self.clients:
            username = self.clients[client_socket]
            # Rimuovi da tutti i gruppi tranne ALL
            for group in self.groups:
                if group != 'ALL' and username in self.groups[group]:
                    self.groups[group].remove(username)
            # Rimuovi da ALL solo quando il client si disconnette completamente
            self.groups['ALL'].remove(username)
            del self.user_groups[username]
            del self.clients[client_socket]
            self.broadcast_to_group({
                'type': 'system',
                'message': f'{username} ha lasciato la chat'
            })

    def start(self):
        """Avvia il server"""
        print(f"{Fore.GREEN}Server avviato su {self.host}:{self.port}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Digita 'help' per vedere i comandi disponibili{Style.RESET_ALL}")
        
        # Thread per gestire i comandi del server
        command_thread = threading.Thread(target=self.handle_server_commands)
        command_thread.daemon = True
        command_thread.start()

        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_thread.daemon = True
                client_thread.start()
            except:
                break

    def handle_server_commands(self):
        """Gestisce i comandi del server"""
        while self.running:
            try:
                command_line = input(f"{Fore.CYAN}Comando server: {Style.RESET_ALL}").strip()
                if not command_line:
                    continue

                parts = command_line.split(' ')
                command = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []

                if command in self.commands:
                    if self.commands[command][1](args):
                        break
                else:
                    print(f"{Fore.RED}Comando non valido. Usa 'help' per vedere i comandi disponibili{Style.RESET_ALL}")
            
            except Exception as e:
                logging.error(f"Errore nel gestore dei comandi: {str(e)}")
                print(f"{Fore.RED}Errore nell'esecuzione del comando: {str(e)}{Style.RESET_ALL}")

if __name__ == '__main__':
    server = Server()
    server.start() 