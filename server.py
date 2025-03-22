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
        self.running = True
        self.commands = {
            'help': ('Mostra questo messaggio di aiuto', self.show_help),
            'list': ('Mostra la lista degli utenti connessi', self.list_users),
            'broadcast': ('Invia un messaggio a tutti gli utenti (uso: broadcast <messaggio>)', self.server_broadcast),
            'kick': ('Disconnette un utente (uso: kick <username>)', self.kick_user),
            'log': ('Mostra gli ultimi 10 log del server', self.show_logs),
            'stop': ('Arresta il server', self.stop_server)
        }
        logging.info(f"Server avviato su {host}:{port}")

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
        """Invia la lista degli utenti connessi a tutti i client"""
        users = list(self.clients.values())
        for client in self.clients:
            try:
                client.send(json.dumps({
                    'type': 'user_list',
                    'users': users
                }).encode())
            except:
                self.remove_client(client)

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

    def handle_client(self, client_socket):
        """Gestisce la connessione di un client"""
        try:
            # Ricezione username
            username = client_socket.recv(1024).decode()
            
            # Verifica se l'username è valido
            if not username or not username.strip():
                client_socket.send(json.dumps({
                    'type': 'username_invalid',
                    'message': 'Username non valido'
                }).encode())
                client_socket.close()
                return
                
            # Verifica se l'username contiene caratteri non validi
            if not all(c.isalnum() or c == '_' for c in username):
                client_socket.send(json.dumps({
                    'type': 'username_invalid',
                    'message': 'Username può contenere solo lettere, numeri e underscore'
                }).encode())
                client_socket.close()
                return
            
            # Verifica se l'username è già in uso
            if self.is_username_taken(username):
                client_socket.send(json.dumps({
                    'type': 'username_taken',
                    'message': 'Username già in uso'
                }).encode())
                client_socket.close()
                return
            
            # Username accettato
            client_socket.send(json.dumps({
                'type': 'username_accepted',
                'message': 'Username accettato'
            }).encode())
            
            self.clients[client_socket] = username
            logging.info(f"Nuovo client connesso: {username}")
            
            # Invia la lista degli utenti al nuovo client
            try:
                client_socket.send(json.dumps({
                    'type': 'user_list',
                    'users': list(self.clients.values())
                }).encode())
            except:
                logging.error(f"Errore nell'invio della lista utenti a {username}")
            
            # Notifica a tutti i client
            self.broadcast({
                'type': 'system',
                'message': f"{username} si è unito alla chat"
            })
            
            # Invia la lista aggiornata degli utenti a tutti
            self.broadcast_user_list()

            while self.running:
                try:
                    message = client_socket.recv(1024).decode()
                    if not message:
                        break

                    data = json.loads(message)
                    
                    if data['type'] == 'disconnect':
                        break
                    elif data['type'] == 'request_users':
                        # Invia la lista degli utenti solo al client che l'ha richiesta
                        try:
                            client_socket.send(json.dumps({
                                'type': 'user_list',
                                'users': list(self.clients.values())
                            }).encode())
                        except:
                            break
                    elif data['type'] == 'broadcast':
                        self.broadcast({
                            'type': 'message',
                            'from': username,
                            'message': data['message']
                        }, client_socket)
                        logging.info(f"Broadcast da {username}: {data['message']}")
                    elif data['type'] == 'private':
                        self.send_private_message(client_socket, data['to'], data['message'])
                        logging.info(f"Messaggio privato da {username} a {data['to']}: {data['message']}")

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logging.error(f"Errore nella gestione del messaggio da {username}: {str(e)}")
                    break

        except Exception as e:
            logging.error(f"Errore nella gestione del client {username if 'username' in locals() else 'sconosciuto'}: {str(e)}")
        finally:
            self.remove_client(client_socket)

    def remove_client(self, client_socket):
        """Rimuove un client dalla lista dei client connessi"""
        if client_socket in self.clients:
            username = self.clients[client_socket]
            del self.clients[client_socket]
            client_socket.close()
            logging.info(f"Client disconnesso: {username}")
            self.broadcast({
                'type': 'system',
                'message': f"{username} ha lasciato la chat"
            })
            # Invia la lista aggiornata degli utenti a tutti
            self.broadcast_user_list()

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

if __name__ == '__main__':
    server = Server()
    server.start() 