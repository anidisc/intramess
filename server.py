import socket
import threading
import json
import logging
from datetime import datetime
from colorama import init, Fore, Style

# Inizializzazione colorama per i colori nel terminale
init()

class ChatServer:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.clients = {}  # socket -> username
        self.groups = {'ALL': set()}  # group -> set of usernames
        self.user_groups = {}  # username -> group
        self.tasks = []  # Lista dei task
        self.task_id_counter = 1  # Inizia da 1 invece che 0
        self.running = True
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('server.log'),
                logging.StreamHandler()
            ]
        )

    def start(self):
        """Avvia il server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logging.info(f"Server avviato su {self.host}:{self.port}")
            logging.info("Server avviato con gruppo predefinito 'ALL'")
            
            # Avvia thread per accettare connessioni
            accept_thread = threading.Thread(target=self.accept_connections)
            accept_thread.daemon = True
            accept_thread.start()
            
            # Loop principale per i comandi del server
            print("Server avviato. Digita 'help' per la lista dei comandi.")
            while self.running:
                try:
                    command = input("Comando server: ").strip()
                    if command:
                        if self.handle_command(command):
                            break
                except KeyboardInterrupt:
                    print("\nChiusura server...")
                    self.stop()
                    break
                except Exception as e:
                    print(f"Errore: {e}")
            
        except Exception as e:
            logging.error(f"Errore avvio server: {e}")
        finally:
            self.server_socket.close()

    def accept_connections(self):
        """Gestisce le connessioni in entrata"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.running:
                    logging.error(f"Errore accettazione connessione: {e}")

    def stop(self):
        """Arresta il server"""
        self.running = False
        # Chiudi tutte le connessioni client
        for client_socket in list(self.clients.keys()):
            try:
                client_socket.close()
            except:
                pass
        # Chiudi il socket del server
        try:
            self.server_socket.close()
        except:
            pass
        logging.info("Server arrestato")

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

    def create_group(self, group_name):
        """Crea un nuovo gruppo"""
        # Converti il nome del gruppo in maiuscolo
        group_name = group_name.upper()
        
        # Verifica se il gruppo esiste già
        if group_name in self.groups:
            print(f"DEBUG: Gruppo {group_name} già esistente")  # Debug
            return False
        
        # Crea il nuovo gruppo
        try:
            self.groups[group_name] = set()
            logging.info(f"Nuovo gruppo creato: {group_name}")
            print(f"DEBUG: Creato nuovo gruppo {group_name}")  # Debug
            
            # Notifica tutti i client del nuovo gruppo
            self.broadcast_to_group({
                'type': 'system',
                'message': f'Nuovo gruppo creato: {group_name}'
            })
            
            # Invia la lista aggiornata dei gruppi a tutti i client
            for client_socket in self.clients:
                try:
                    client_socket.send(json.dumps({
                        'type': 'connection_accepted',
                        'groups': list(self.groups.keys())
                    }).encode() + b'\n')
                except:
                    self.remove_client(client_socket)
                
            return True
        except Exception as e:
            logging.error(f"Errore creazione gruppo {group_name}: {e}")
            return False

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

    def create_task(self, creator, group, text, requester_group):
        """Crea un nuovo task con ID univoco"""
        task = {
            'id': f"T{self.task_id_counter:04d}",  # Format: T0001, T0002, etc.
            'text': text,
            'group': group,
            'created_by': creator,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'completed': False,
            'completed_by': None,
            'completed_date': None,
            'requester_group': requester_group  # Aggiungi il gruppo richiedente
        }
        self.tasks.append(task)
        self.task_id_counter += 1
        print(f"DEBUG: Task creato: {task}")
        self.broadcast_tasks()
        return task

    def complete_task(self, task_id, username):
        for task in self.tasks:
            if task['id'] == task_id:
                if username in self.groups[task['group']]:
                    task['completed'] = True
                    self.broadcast_tasks()
                    return True
        return False

    def broadcast_tasks(self):
        """Invia la lista dei task aggiornata a tutti i client"""
        print(f"DEBUG: Invio lista task aggiornata: {self.tasks}")  # Debug
        message = json.dumps({
            'type': 'task_list',
            'tasks': self.tasks
        }) + '\n'
        
        for client_socket in self.clients:
            try:
                client_socket.send(message.encode())
                print(f"DEBUG: Lista task inviata a {self.clients[client_socket]}")  # Debug
            except Exception as e:
                print(f"DEBUG: Errore invio task a {self.clients[client_socket]}: {e}")  # Debug
                self.remove_client(client_socket)

    def update_task(self, task_id, username, completed):
        """Aggiorna lo stato di un task"""
        for task in self.tasks:
            if task['id'] == task_id:
                if username in self.groups[task['group']]:
                    task['completed'] = completed
                    if completed:
                        task['completed_by'] = username
                        task['completed_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    else:
                        task['completed_by'] = None
                        task['completed_date'] = None
                    
                    # Notifica tutti dell'aggiornamento
                    self.broadcast_to_group({
                        'type': 'system',
                        'message': f"Task #{task['id']} '{task['text']}' {'completato' if completed else 'riaperto'} da {username}"
                    })
                    
                    self.broadcast_tasks()
                    return True
        return False

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

            # Invia la lista dei task subito dopo la connessione
            self.broadcast_tasks()

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

                        if data['type'] == 'disconnect':
                            print(f"DEBUG: Disconnessione richiesta da {username}")
                            raise ConnectionResetError  # Forza l'uscita dal loop
                        
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

                        elif data['type'] == 'create_task':
                            if data['group'] != self.user_groups[username] and data['group'] != 'ALL':
                                task = self.create_task(
                                    username, 
                                    data['group'], 
                                    data['text'],
                                    data.get('requester_group', 'N/A')  # Aggiungi il gruppo richiedente
                                )
                                print(f"DEBUG: Nuovo task creato da {username}: {task}")  # Debug
                                self.broadcast_to_group({
                                    'type': 'system',
                                    'message': f'{username} ha creato un nuovo task per il gruppo {data["group"]}'
                                })

                        elif data['type'] == 'complete_task':
                            if self.complete_task(data['task_id'], username):
                                print(f"DEBUG: Task {data['task_id']} completato da {username}")  # Debug
                                self.broadcast_to_group({
                                    'type': 'system',
                                    'message': f'{username} ha completato un task'
                                })

                        elif data['type'] == 'update_task':
                            if self.update_task(data['task_id'], username, data['completed']):
                                print(f"DEBUG: Task {data['task_id']} {'completato' if data['completed'] else 'riaperto'} da {username}")

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
            
            # Se è un messaggio di gruppo, aggiungi il mittente ai destinatari
            if message.get('type') == 'message':
                sender = message.get('from')
                if sender:
                    recipients.add(sender)

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
        """Rimuove un client e aggiorna tutti gli altri"""
        if client_socket in self.clients:
            username = self.clients[client_socket]
            print(f"DEBUG: Rimozione client {username}")
            
            # Rimuovi da tutti i gruppi
            for group in self.groups.values():
                group.discard(username)
            
            # Rimuovi dal dizionario dei gruppi utente
            if username in self.user_groups:
                del self.user_groups[username]
            
            # Rimuovi dal dizionario dei client
            del self.clients[client_socket]
            
            try:
                client_socket.close()
            except:
                pass
            
            # Notifica tutti della disconnessione
            self.broadcast_to_group({
                'type': 'system',
                'message': f'{username} ha lasciato la chat'
            })
            
            # Aggiorna la lista utenti per tutti
            self.broadcast_user_list()
            
            print(f"DEBUG: Client {username} rimosso con successo")

    def handle_command(self, command):
        parts = command.split()
        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        # Dizionario dei comandi e loro alias
        commands = {
            'creategroup': ['creategroup', 'cg'],
            'listgroups': ['listgroups', 'lg'],
            'removegroup': ['removegroup', 'rg'],
            'kick': ['kick', 'k'],
            'list': ['list', 'l'],
            'help': ['help', 'h'],
            'quit': ['quit', 'q', 'exit']
        }

        try:
            # Trova il comando effettivo dall'alias usato
            actual_command = None
            for cmd_name, aliases in commands.items():
                if cmd in aliases:
                    actual_command = cmd_name
                    break

            if actual_command == 'creategroup':
                if len(args) != 1:
                    print("Uso: creategroup|cg <nome_gruppo>")
                    return
                # Passa l'intero nome del gruppo, non solo il primo carattere
                group_name = args[0]
                if self.create_group(group_name):
                    print(f"Gruppo {group_name.upper()} creato con successo")
                else:
                    print(f"Gruppo {group_name.upper()} già esistente")

            elif actual_command == 'listgroups':
                print("Gruppi disponibili:")
                for group, members in self.groups.items():
                    print(f"- {group}: {len(members)} utenti")
                    for member in sorted(members):
                        print(f"  • {member}")

            elif actual_command == 'removegroup':
                if len(args) != 1:
                    print("Uso: removegroup|rg <nome_gruppo>")
                    return
                group_name = args[0].upper()
                if group_name == 'ALL':
                    print("Non puoi rimuovere il gruppo ALL")
                    return
                if group_name in self.groups:
                    del self.groups[group_name]
                    # Sposta gli utenti nel gruppo ALL
                    for username, group in self.user_groups.items():
                        if group == group_name:
                            self.user_groups[username] = 'ALL'
                    print(f"Gruppo {group_name} rimosso")
                else:
                    print(f"Gruppo {group_name} non trovato")

            elif actual_command == 'kick':
                if len(args) != 1:
                    print("Uso: kick|k <username>")
                    return
                username = args[0]
                kicked = False
                # Trova il socket dell'utente
                for client_socket, name in list(self.clients.items()):  # Usa una copia della lista
                    if name == username:
                        print(f"DEBUG: Trovato utente {username} da espellere")
                        self.broadcast_to_group({
                            'type': 'system',
                            'message': f'{username} è stato espulso dal server'
                        })
                        try:
                            client_socket.send(json.dumps({
                                'type': 'kicked',
                                'message': 'Sei stato espulso dal server'
                            }).encode() + b'\n')
                            client_socket.close()
                        except:
                            pass
                        self.remove_client(client_socket)
                        kicked = True
                        break
                
                if kicked:
                    print(f"Utente {username} espulso con successo")
                else:
                    print(f"Utente {username} non trovato")

            elif actual_command == 'list':
                print("Client connessi:")
                for username in sorted(self.clients.values()):
                    print(f"- {username}")

            elif actual_command == 'help':
                print("Comandi disponibili:")
                print("- creategroup|cg <nome_gruppo> : Crea un nuovo gruppo")
                print("- listgroups|lg : Mostra i gruppi e i loro membri")
                print("- removegroup|rg <nome_gruppo> : Rimuove un gruppo")
                print("- kick|k <username> : Espelle un utente")
                print("- list|l : Mostra gli utenti connessi")
                print("- help|h : Mostra questo messaggio")
                print("- quit|q|exit : Chiude il server")

            elif actual_command == 'quit':
                self.stop()
                return True

            else:
                print(f"Comando non riconosciuto. Digita 'help' per la lista dei comandi")

        except Exception as e:
            print(f"Errore nell'esecuzione del comando: {e}")
            logging.error(f"Errore comando: {e}")

        return False

def main():
    server = ChatServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nArresto del server...")
    finally:
        server.stop()

if __name__ == "__main__":
    main() 