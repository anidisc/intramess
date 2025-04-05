from pymongo import MongoClient
import hashlib
import os
from datetime import datetime
import json

class Database:
    def __init__(self, config_file=None):
        # Carica la configurazione
        try:
            if config_file:
                print(f"DEBUG Database: Utilizzo file di configurazione personalizzato: {config_file}")
                with open(config_file, 'r') as f:
                    config = json.load(f)
            else:
                print("DEBUG Database: Utilizzo file di configurazione predefinito: config.json")
                with open('config.json', 'r') as f:
                    config = json.load(f)
                
            db_config = config['database']
            
            # Salva host e porta per poterli esporre al server
            self.host = db_config['host']
            self.port = db_config['port']
            
            print(f"DEBUG Database: Connessione a {self.host}:{self.port}")
        
            # Costruisci l'URI di connessione con le credenziali
            mongo_uri = f"mongodb://{db_config['username']}:{db_config['password']}@{self.host}:{self.port}/"
        
            # Connessione a MongoDB
            self.client = MongoClient(mongo_uri)
            # Seleziona il database
            self.db = self.client[db_config['database']]
            # Seleziona la collezione users
            self.users = self.db.users
            # Seleziona la collezione groups
            self.groups = self.db.groups
            # Seleziona la collezione tasks
            self.tasks = self.db.tasks
            # Seleziona la collezione chats
            self.chats = self.db.chats
            
            # Crea un indice unico sull'username
            self.users.create_index('username', unique=True)
            # Crea un indice unico sul nome del gruppo
            self.groups.create_index('name', unique=True)
            # Crea un indice unico sull'ID del task
            self.tasks.create_index('id', unique=True)
            # Crea un indice sulla data per i messaggi
            self.chats.create_index([('timestamp', 1)])
            
            print("DEBUG: Connessione al database stabilita con successo")
            
        except Exception as e:
            print(f"DEBUG: Errore connessione al database: {str(e)}")
            raise
    
    def hash_password(self, password):
        """Genera un hash sicuro della password"""
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return salt + key
    
    def verify_password(self, stored_password, password):
        """Verifica se la password corrisponde all'hash memorizzato"""
        salt = stored_password[:32]
        stored_key = stored_password[32:]
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return key == stored_key
    
    def register_user(self, username, password):
        """Registra un nuovo utente nel database"""
        try:
            # Verifica se l'utente esiste già
            if self.user_exists(username):
                return False, "Username già in uso"
            
            # Genera il salt e l'hash della password
            salt = os.urandom(32)
            key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                100000
            )
            
            # Prepara il documento utente
            user_doc = {
                'username': username,
                'password': key.hex(),
                'salt': salt.hex(),
                'created_at': datetime.now()
            }
            
            print(f"DEBUG: Tentativo di registrazione utente: {username}")
            
            # Inserisci l'utente nel database
            result = self.users.insert_one(user_doc)
            
            if result.inserted_id:
                print(f"DEBUG: Utente registrato con successo: {username}")
                return True, "Utente registrato con successo"
            else:
                print(f"DEBUG: Errore durante la registrazione: {username}")
                return False, "Errore durante la registrazione"
                
        except Exception as e:
            print(f"DEBUG: Eccezione durante la registrazione: {str(e)}")
            return False, f"Errore durante la registrazione: {str(e)}"
    
    def login_user(self, username, password):
        """Verifica le credenziali di login"""
        try:
            # Cerca l'utente nel database
            user = self.users.find_one({'username': username})
            
            if not user:
                return False, "Utente non trovato"
            
            # Verifica la password
            salt = bytes.fromhex(user['salt'])
            key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                100000
            )
            
            if key.hex() == user['password']:
                return True, "Login effettuato con successo"
            else:
                return False, "Password non valida"
                
        except Exception as e:
            print(f"DEBUG: Errore durante il login: {str(e)}")
            return False, f"Errore durante il login: {str(e)}"
    
    def delete_user(self, username):
        """Elimina un utente dal database"""
        try:
            result = self.users.delete_one({'username': username})
            if result.deleted_count > 0:
                return True, f"Utente {username} eliminato con successo"
            else:
                return False, f"Utente {username} non trovato"
        except Exception as e:
            return False, f"Errore durante l'eliminazione: {str(e)}"
    
    def user_exists(self, username):
        """Verifica se un utente esiste"""
        return self.users.find_one({'username': username}) is not None
    
    def get_all_users(self):
        """Ottiene la lista di tutti gli utenti registrati"""
        try:
            print("DEBUG: Tentativo di recupero utenti dal database")
            users = list(self.users.find({}, {'username': 1, 'created_at': 1, '_id': 0}))
            print(f"DEBUG: Utenti trovati: {users}")
            return True, users
        except Exception as e:
            print(f"DEBUG: Errore nel recupero utenti: {str(e)}")
            return False, f"Errore durante il recupero degli utenti: {str(e)}"
    
    def save_group(self, group_name):
        """Salva un gruppo nel database (solo il nome)"""
        try:
            # Verifica se il gruppo esiste già
            existing_group = self.groups.find_one({'name': group_name})
            
            if existing_group:
                print(f"DEBUG: Gruppo {group_name} già presente nel database")
                return True, f"Gruppo {group_name} già esistente"
            else:
                # Crea un nuovo gruppo
                group_doc = {
                    'name': group_name,
                    'created_at': datetime.now()
                }
                result = self.groups.insert_one(group_doc)
                if result.inserted_id:
                    print(f"DEBUG: Gruppo {group_name} salvato nel database")
                    return True, f"Gruppo {group_name} salvato"
                else:
                    print(f"DEBUG: Errore nel salvataggio del gruppo {group_name}")
                    return False, f"Errore nel salvataggio del gruppo {group_name}"
        except Exception as e:
            print(f"DEBUG: Errore durante il salvataggio del gruppo: {str(e)}")
            return False, f"Errore durante il salvataggio del gruppo: {str(e)}"
    
    def delete_group(self, group_name):
        """Elimina un gruppo dal database"""
        try:
            result = self.groups.delete_one({'name': group_name})
            if result.deleted_count > 0:
                print(f"DEBUG: Gruppo {group_name} eliminato dal database")
                return True, f"Gruppo {group_name} eliminato"
            else:
                print(f"DEBUG: Gruppo {group_name} non trovato nel database")
                return False, f"Gruppo {group_name} non trovato"
        except Exception as e:
            print(f"DEBUG: Errore durante l'eliminazione del gruppo: {str(e)}")
            return False, f"Errore durante l'eliminazione del gruppo: {str(e)}"
    
    def get_all_groups(self):
        """Ottiene tutti i nomi dei gruppi dal database"""
        try:
            groups = []
            for group in self.groups.find():
                groups.append(group['name'])
            print(f"DEBUG: Gruppi caricati dal database: {groups}")
            return True, groups
        except Exception as e:
            print(f"DEBUG: Errore durante il recupero dei gruppi: {str(e)}")
            return False, f"Errore durante il recupero dei gruppi: {str(e)}"
    
    def save_task(self, task):
        """Salva un task nel database"""
        try:
            # Converti le date string in oggetti datetime se necessario
            task_copy = task.copy()  # Crea una copia per non modificare l'originale
            
            # Verifica se il task esiste già
            existing_task = self.tasks.find_one({'id': task_copy['id']})
            
            if existing_task:
                # Aggiorna il task esistente
                result = self.tasks.update_one(
                    {'id': task_copy['id']},
                    {'$set': task_copy}
                )
                if result.modified_count > 0:
                    print(f"DEBUG: Task {task_copy['id']} aggiornato nel database")
                    return True, f"Task {task_copy['id']} aggiornato"
                else:
                    print(f"DEBUG: Nessuna modifica al task {task_copy['id']}")
                    return True, f"Nessuna modifica al task {task_copy['id']}"
            else:
                # Crea un nuovo task
                result = self.tasks.insert_one(task_copy)
                if result.inserted_id:
                    print(f"DEBUG: Task {task_copy['id']} salvato nel database")
                    return True, f"Task {task_copy['id']} salvato"
                else:
                    print(f"DEBUG: Errore nel salvataggio del task {task_copy['id']}")
                    return False, f"Errore nel salvataggio del task {task_copy['id']}"
        except Exception as e:
            print(f"DEBUG: Errore durante il salvataggio del task: {str(e)}")
            return False, f"Errore durante il salvataggio del task: {str(e)}"
    
    def delete_task(self, task_id):
        """Elimina un task dal database"""
        try:
            result = self.tasks.delete_one({'id': task_id})
            if result.deleted_count > 0:
                print(f"DEBUG: Task {task_id} eliminato dal database")
                return True, f"Task {task_id} eliminato"
            else:
                print(f"DEBUG: Task {task_id} non trovato nel database")
                return False, f"Task {task_id} non trovato"
        except Exception as e:
            print(f"DEBUG: Errore durante l'eliminazione del task: {str(e)}")
            return False, f"Errore durante l'eliminazione del task: {str(e)}"
    
    def get_all_tasks(self):
        """Ottiene tutti i task dal database"""
        try:
            tasks = list(self.tasks.find({}, {'_id': 0}))
            print(f"DEBUG: {len(tasks)} task caricati dal database")
            return True, tasks
        except Exception as e:
            print(f"DEBUG: Errore durante il recupero dei task: {str(e)}")
            return False, f"Errore durante il recupero dei task: {str(e)}"
    
    def save_message(self, group_name, message_text, sender, users_in_group):
        """Salva un messaggio nella collezione chats"""
        try:
            # Crea il documento del messaggio
            message_doc = {
                'text': message_text,
                'sender': sender,
                'group': group_name,
                'users_in_group': users_in_group,
                'timestamp': datetime.now()
            }
            
            # Salva nella collezione chats
            self.chats.insert_one(message_doc)
            
            print(f"DEBUG: Messaggio salvato per il gruppo {group_name} nella collezione chats")
            return True
        except Exception as e:
            print(f"DEBUG: Errore durante il salvataggio del messaggio: {str(e)}")
            return False
            
    def get_group_messages(self, group_name, limit=100):
        """Ottiene gli ultimi messaggi di un gruppo specifico dalla collezione chats"""
        try:
            # Ottieni i messaggi del gruppo dalla collezione chats
            messages = list(self.chats.find({'group': group_name}).sort('timestamp', -1).limit(limit))
            
            # Inverte l'ordine per avere i messaggi dal più vecchio al più recente
            messages.reverse()
            
            return True, messages
        except Exception as e:
            print(f"DEBUG: Errore durante il recupero dei messaggi: {str(e)}")
            return False, []
    
    def get_user_historical_messages(self, username):
        """Ottiene tutti i messaggi dei gruppi in cui l'utente è stato presente"""
        try:
            # Trova tutti i messaggi dove l'utente era nella lista users_in_group
            messages = list(self.chats.find(
                {'users_in_group': username}
            ).sort('timestamp', 1))  # Ordina per timestamp in ordine crescente
            
            # Converti gli oggetti datetime in stringhe per la serializzazione JSON
            for msg in messages:
                if '_id' in msg:
                    del msg['_id']  # Rimuovi l'ObjectId di MongoDB che non è serializzabile
                if 'timestamp' in msg and isinstance(msg['timestamp'], datetime):
                    msg['timestamp'] = msg['timestamp'].isoformat()
            
            # Raggruppa i messaggi per gruppo
            messages_by_group = {}
            for msg in messages:
                group = msg['group']
                if group not in messages_by_group:
                    messages_by_group[group] = []
                messages_by_group[group].append(msg)
            
            print(f"DEBUG: Trovati messaggi storici per l'utente {username} in {len(messages_by_group)} gruppi")
            return True, messages_by_group
        except Exception as e:
            print(f"DEBUG: Errore durante il recupero dei messaggi storici: {str(e)}")
            return False, {} 