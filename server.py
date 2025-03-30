import socket
import threading
import json
import logging
from datetime import datetime
from colorama import init, Fore, Style
from database import Database

# Inizializzazione colorama per i colori nel terminale
init()

class ChatServer:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = {}  # socket -> username
        self.groups = {'ALL': set()}  # group -> set of usernames
        self.user_groups = {}  # username -> group
        self.tasks = []  # Lista dei task
        self.task_id_counter = 1  # Inizia da 1 invece che 0
        self.running = True
        self.setup_logging()
        self.db = Database()
        self.connected_users = set()  # Set di utenti attualmente connessi
        
        # Carica i gruppi dal database
        self.load_groups_from_db()
        
        # Carica i task dal database
        self.load_tasks_from_db()
        
        # Dizionario dei comandi disponibili
        self.commands = {
            'help': {'alias': 'h', 'description': 'Mostra l\'elenco dei comandi disponibili', 'func': self.show_help},
            'list': {'alias': 'l', 'description': 'Mostra la lista degli utenti connessi', 'func': self.list_users},
            'broadcast': {'alias': 'b', 'description': 'Invia un messaggio a tutti gli utenti', 'func': self.server_broadcast},
            'broadcast_group': {'alias': 'bg', 'description': 'Invia un messaggio a un gruppo specifico', 'func': self.broadcast_to_group_command},
            'private': {'alias': 'p', 'description': 'Invia un messaggio privato a un utente', 'func': self.private_message_command},
            'showlog': {'alias': 'log', 'description': 'Mostra gli ultimi log del server', 'func': self.show_logs},
            'kick': {'alias': 'k', 'description': 'Disconnette un utente specificato', 'func': self.kick_user},
            'creategroup': {'alias': 'cg', 'description': 'Crea un nuovo gruppo', 'func': self.create_group},
            'deletegroup': {'alias': 'dg', 'description': 'Elimina un gruppo esistente', 'func': self.delete_group},
            'listgroups': {'alias': 'lg', 'description': 'Mostra la lista dei gruppi', 'func': self.list_groups},
            'deleteuser': {'alias': 'du', 'description': 'Elimina un utente dal database', 'func': self.delete_user_command},
            'list_users': {'alias': 'lu', 'description': 'Mostra tutti gli utenti registrati nel database', 'func': self.list_users_command},
            'quit': {'alias': 'q', 'description': 'Chiude il server', 'func': self.stop}
        }

    def setup_logging(self):
        """Configura il logger"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('server.log'),
                logging.StreamHandler()
            ]
        )

    def load_groups_from_db(self):
        """Carica i gruppi dal database"""
        logging.info("Caricamento gruppi dal database...")
        success, result = self.db.get_all_groups()
        
        if success:
            # Crea i gruppi dal database (solo i nomi)
            for group_name in result:
                if group_name != 'ALL' and group_name not in self.groups:
                    self.groups[group_name] = set()
                    logging.info(f"Gruppo caricato dal database: {group_name}")
            
            logging.info(f"Gruppi caricati dal database: {list(self.groups.keys())}")
        else:
            logging.error(f"Errore nel caricamento dei gruppi: {result}")

    def load_tasks_from_db(self):
        """Carica i task dal database"""
        logging.info("Caricamento task dal database...")
        success, result = self.db.get_all_tasks()
        
        if success:
            # Carica tutti i task dal database
            self.tasks = result
            
            # Determina il valore iniziale del contatore dei task
            if self.tasks:
                # Trova l'ID numerico più alto tra i task esistenti
                max_id = 0
                for task in self.tasks:
                    try:
                        # Estrai il numero dall'ID (formato Txxxx)
                        task_num = int(task['id'][1:])
                        max_id = max(max_id, task_num)
                    except:
                        pass
                
                # Imposta il contatore al valore massimo + 1
                self.task_id_counter = max_id + 1
                
            logging.info(f"Caricati {len(self.tasks)} task dal database. Prossimo ID: T{self.task_id_counter:04d}")
        else:
            logging.error(f"Errore nel caricamento dei task: {result}")

    def start(self):
        """Avvia il server"""
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
                    args=(client_socket, address)
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
        for cmd, info in self.commands.items():
            aliases_str = f" ({info['alias']})" if info['alias'] else ""
            print(f"- {Fore.CYAN}{cmd}{aliases_str}{Style.RESET_ALL}: {info['description']}")

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
                'group': self.user_groups.get(username, 'N/A')
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
                    'from': username,
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
            
            # Salva il gruppo nel database (solo il nome)
            success, message = self.db.save_group(group_name)
            if not success:
                logging.error(f"Errore nel salvataggio del gruppo nel database: {message}")
            
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
        
        # Trova tutti i task associati al gruppo
        tasks_to_delete = [task for task in self.tasks if task['group'] == group_name]
        incomplete_tasks = [task for task in tasks_to_delete if not task['completed']]
        
        # Mostra i task non completati che verranno eliminati
        if incomplete_tasks:
            print(f"{Fore.YELLOW}Attenzione: I seguenti task non completati assegnati al gruppo {group_name} verranno eliminati:{Style.RESET_ALL}")
            for task in incomplete_tasks:
                print(f"- [{task['id']}] {task['text']} (creato da: {task['created_by']})")
        else:
            if tasks_to_delete:
                print(f"{Fore.YELLOW}Attenzione: Verranno eliminati {len(tasks_to_delete)} task completati associati al gruppo {group_name}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}Non ci sono task associati al gruppo {group_name}{Style.RESET_ALL}")
        
        # Richiedi conferma prima di eliminare
        confirm = input(f"{Fore.YELLOW}Sei sicuro di voler eliminare il gruppo {group_name} e tutti i task associati? (s/n): {Style.RESET_ALL}")
        if confirm.lower() != 's':
            print(f"{Fore.YELLOW}Eliminazione del gruppo {group_name} annullata{Style.RESET_ALL}")
            return
            
        # Sposta gli utenti del gruppo eliminato nel gruppo ALL
        for username in self.groups[group_name]:
            self.groups['ALL'].add(username)
            self.user_groups[username] = 'ALL'
        
        # Elimina tutti i task associati al gruppo
        if tasks_to_delete:
            for task in tasks_to_delete:
                # Rimuovi il task dalla lista dei task
                self.tasks.remove(task)
                # Elimina il task dal database
                success, message = self.db.delete_task(task['id'])
                if not success:
                    logging.error(f"Errore nell'eliminazione del task {task['id']} dal database: {message}")
            
            print(f"{Fore.GREEN}{len(tasks_to_delete)} task associati al gruppo {group_name} eliminati{Style.RESET_ALL}")
        
        # Elimina il gruppo
        del self.groups[group_name]
        
        # Elimina il gruppo dal database
        success, message = self.db.delete_group(group_name)
        if not success:
            logging.error(f"Errore nell'eliminazione del gruppo dal database: {message}")
        
        print(f"{Fore.GREEN}Gruppo {group_name} eliminato{Style.RESET_ALL}")
        logging.info(f"Gruppo eliminato: {group_name} con {len(tasks_to_delete)} task associati")
        
        # Invia un messaggio specifico per l'eliminazione del gruppo
        for client_socket in self.clients:
            try:
                client_socket.send(json.dumps({
                    'type': 'group_deleted',
                    'group_name': group_name,
                    'message': f'Il gruppo {group_name} è stato eliminato'
                }).encode())
            except:
                self.remove_client(client_socket)
        
        # Notifica tutti i client
        self.broadcast_groups()
        
        # Aggiorna la lista dei task su tutti i client
        if tasks_to_delete:
            self.broadcast_tasks()

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
        
        # Salva il task nel database
        success, message = self.db.save_task(task)
        if not success:
            logging.error(f"Errore nel salvataggio del task nel database: {message}")
        
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
                    
                    # Salva le modifiche nel database
                    success, message = self.db.save_task(task)
                    if not success:
                        logging.error(f"Errore nell'aggiornamento del task nel database: {message}")
                    
                    # Notifica tutti dell'aggiornamento
                    self.broadcast_to_group({
                        'type': 'system',
                        'message': f"Task #{task['id']} '{task['text']}' {'completato' if completed else 'riaperto'} da {username}"
                    })
                    
                    self.broadcast_tasks()
                    return True
        return False

    def handle_client(self, client_socket, address):
        """Gestisce la connessione di un client"""
        try:
            # Ricevi le credenziali di login/registrazione
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                return
                
            try:
                message = json.loads(data)
                print(f"DEBUG SERVER - Messaggio ricevuto: {message}")
                
                if message['type'] == 'login':
                    username = message['username']
                    password = message['password']
                    
                    print(f"DEBUG SERVER - Tentativo di login per: {username}")
                    success, msg = self.db.login_user(username, password)
                    
                    if success:
                        # Verifica se l'utente è già connesso
                        if username in self.connected_users:
                            client_socket.send(json.dumps({
                                'type': 'error',
                                'message': 'Utente già connesso da un\'altra sessione'
                            }).encode('utf-8'))
                            client_socket.close()
                            return
                        
                        # Aggiungi l'utente alla lista degli utenti connessi
                        self.connected_users.add(username)
                        
                        # Registra il client
                        self.clients[client_socket] = username
                        self.groups['ALL'].add(username)
                        self.user_groups[username] = 'ALL'
                        
                        # Invia conferma al client
                        client_socket.send(json.dumps({
                            'type': 'connection_accepted',
                            'groups': list(self.groups.keys()),
                            'message': msg
                        }).encode('utf-8'))
                        
                        # Notifica tutti della nuova connessione
                        self.broadcast_to_group({
                            'type': 'system',
                            'message': f'{username} si è unito alla chat'
                        })
                        
                        # Invia lista utenti a tutti
                        self.broadcast_user_list()
                        
                        # Invia la lista dei task
                        self.broadcast_tasks()
                        
                        # Avvia il loop principale per i messaggi
                        self.handle_client_messages(client_socket, username)
                    else:
                        client_socket.send(json.dumps({
                            'type': 'error',
                            'message': msg
                        }).encode('utf-8'))
                        client_socket.close()
                        return
            except Exception as e:
                print(f"Errore nel parsing del messaggio: {e}")
                client_socket.close()
                return
        except Exception as e:
            logging.error(f"Errore gestione client: {e}")
        finally:
            if client_socket in self.clients:
                self.remove_client(client_socket)

    def handle_client_messages(self, client_socket, username):
        """Gestisce i messaggi del client"""
        while self.running:
            try:
                data = client_socket.recv(4096).decode('utf-8')
                if not data:
                    break
                
                try:
                    data = json.loads(data)
                    print(f"DEBUG: Ricevuto messaggio da {username}: {data}")
                    
                    if data['type'] == 'disconnect':
                        break
                    
                    elif data['type'] == 'delete_task':
                        task_id = data['task_id']
                        # Cerca il task e verifica che l'utente sia il creatore
                        for task in self.tasks:
                            if task['id'] == task_id and task['created_by'] == username:
                                # Rimuovi il task dalla lista
                                self.tasks.remove(task)
                                
                                # Elimina il task dal database
                                success, message = self.db.delete_task(task_id)
                                if not success:
                                    logging.error(f"Errore nell'eliminazione del task dal database: {message}")
                                
                                print(f"DEBUG: Task {task_id} eliminato da {username}")
                                self.broadcast_to_group({
                                    'type': 'system',
                                    'message': f'{username} ha eliminato un task'
                                })
                                self.broadcast_tasks()
                                break
                        continue
                    
                    elif data['type'] == 'request_users':
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
                            
                            # Non è più necessario aggiornare i membri nel database
                            
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
                                self.user_groups[username]
                            )
                            # Notifica gli utenti del gruppo del nuovo task
                            self.broadcast_to_group({
                                'type': 'system',
                                'message': f'Nuovo task assegnato da {username}: {data["text"]}'
                            }, group=data['group'])
                    
                    elif data['type'] == 'update_task':
                        task_id = data['task_id']
                        completed = data['completed']
                        if self.update_task(task_id, username, completed):
                            print(f"DEBUG: Task {task_id} aggiornato da {username}")
                
                except json.JSONDecodeError:
                    print(f"DEBUG: Errore parsing JSON: {data}")
                except Exception as e:
                    print(f"DEBUG: Errore gestione client {username}: {e}")
                    break
            
            except Exception as e:
                print(f"DEBUG: Errore connessione client {username}: {e}")
                break
        
        # Disconnessione del client
        self.remove_client(client_socket)

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
            
            # Rimuovi l'utente dalla lista degli utenti connessi
            if username in self.connected_users:
                self.connected_users.remove(username)
            
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
        """Gestisce i comandi del server"""
        try:
            parts = command.split()
            if not parts:
                return False
                
            cmd = parts[0].lower()
            args = parts[1:]
            
            # Cerca il comando effettivo basato sull'alias
            actual_command = None
            for cmd_name, info in self.commands.items():
                if cmd in [cmd_name, info['alias']]:
                    actual_command = cmd_name
                    break
            
            if actual_command:
                self.commands[actual_command]['func'](*args)
                return actual_command == 'quit'
            else:
                print(f"{Fore.RED}Comando non riconosciuto. Digita 'help' per la lista dei comandi{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}Errore nell'esecuzione del comando: {str(e)}{Style.RESET_ALL}")
            logging.error(f"Errore comando {cmd}: {e}")
            return False

    def broadcast_to_group_command(self, *args):
        """Invia un messaggio a un gruppo specifico"""
        if len(args) < 2:
            print(f"{Fore.RED}Errore: Specificare il gruppo e il messaggio{Style.RESET_ALL}")
            print("Uso: broadcast_group <gruppo> <messaggio>")
            return
        
        group = args[0].upper()
        message = ' '.join(args[1:])
        
        if group not in self.groups:
            print(f"{Fore.RED}Errore: Gruppo {group} non trovato{Style.RESET_ALL}")
            return
            
        self.broadcast_to_group({
            'type': 'system',
            'message': f"[Server Broadcast a {group}] {message}"
        }, group=group)
        
        logging.info(f"Server broadcast al gruppo {group}: {message}")
        print(f"{Fore.GREEN}Messaggio inviato al gruppo {group}{Style.RESET_ALL}")

    def private_message_command(self, *args):
        """Invia un messaggio privato a un utente specifico"""
        if len(args) < 2:
            print(f"{Fore.RED}Errore: Specificare l'utente e il messaggio{Style.RESET_ALL}")
            print("Uso: private <username> <messaggio>")
            return
        
        recipient = args[0]
        message = ' '.join(args[1:])
        
        if recipient not in self.clients.values():
            print(f"{Fore.RED}Errore: Utente {recipient} non trovato{Style.RESET_ALL}")
            return
            
        # Trova il socket del destinatario
        recipient_socket = next(
            (s for s, u in self.clients.items() if u == recipient),
            None
        )
        
        if recipient_socket:
            try:
                recipient_socket.send(json.dumps({
                    'type': 'system',
                    'message': f"[Server Private Message] {message}"
                }).encode())
                logging.info(f"Server private message a {recipient}: {message}")
                print(f"{Fore.GREEN}Messaggio privato inviato a {recipient}{Style.RESET_ALL}")
            except:
                self.remove_client(recipient_socket)
                print(f"{Fore.RED}Errore: Impossibile inviare il messaggio{Style.RESET_ALL}")

    def delete_user_command(self, *args):
        """Elimina un utente dal database"""
        if not args or not args[0]:
            print(f"{Fore.RED}Errore: Specificare l'username da eliminare{Style.RESET_ALL}")
            print("Uso: deleteuser <username>")
            return
            
        username = args[0]
        success, message = self.db.delete_user(username)
        
        if success:
            print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")
            logging.info(f"Utente eliminato: {username}")
        else:
            print(f"{Fore.RED}{message}{Style.RESET_ALL}")

    def list_users_command(self):
        """Mostra tutti gli utenti registrati nel database"""
        success, result = self.db.get_all_users()
        if success:
            print("\nUtenti registrati:")
            print("-" * 50)
            for user in result:
                created_at = user['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                print(f"Username: {user['username']}")
                print(f"Registrato il: {created_at}")
                print("-" * 50)
        else:
            print(f"\nErrore: {result}")

    def handle_disconnect(self, client_socket):
        if client_socket in self.clients:
            username = self.clients[client_socket]
            group = self.user_groups[username]
            
            # Rimuovi l'utente dalla lista degli utenti connessi
            if username in self.connected_users:
                self.connected_users.remove(username)
            
            # Rimuovi il client dalla lista dei client connessi
            del self.clients[client_socket]
            
            # Rimuovi l'utente dal gruppo
            if group in self.groups:
                if username in self.groups[group]:
                    self.groups[group].remove(username)
                    
                if not self.groups[group]:  # Se il gruppo è vuoto
                    del self.groups[group]
                    # Elimina il gruppo dal database se non è ALL
                    if group != 'ALL':
                        self.db.delete_group(group)
            
            # Invia la lista aggiornata degli utenti a tutti i client
            self.broadcast_user_list()
            
            # Invia messaggio di disconnessione
            self.broadcast_to_group({
                'type': 'system',
                'message': f'{username} ha lasciato la chat'
            })
            
            client_socket.close()

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