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
        logging.info(f"Server avviato su {host}:{port}")

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
            self.clients[client_socket] = username
            logging.info(f"Nuovo client connesso: {username}")
            
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
                    
                    if data['type'] == 'broadcast':
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
            logging.error(f"Errore nella gestione del client {username}: {str(e)}")
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
                command = input(f"{Fore.CYAN}Comando server: {Style.RESET_ALL}")
                
                if command == 'list':
                    print(f"{Fore.YELLOW}Client connessi:{Style.RESET_ALL}")
                    for username in self.clients.values():
                        print(f"- {username}")
                
                elif command.startswith('kick '):
                    username = command[5:]
                    for client, name in self.clients.items():
                        if name == username:
                            self.remove_client(client)
                            print(f"{Fore.GREEN}Utente {username} disconnesso{Style.RESET_ALL}")
                            break
                
                elif command == 'log':
                    try:
                        with open('server.log', 'r') as f:
                            print(f"{Fore.YELLOW}Ultimi log:{Style.RESET_ALL}")
                            for line in f.readlines()[-10:]:
                                print(line.strip())
                    except:
                        print(f"{Fore.RED}Errore nella lettura del file di log{Style.RESET_ALL}")
                
                elif command == 'stop':
                    self.running = False
                    print(f"{Fore.RED}Arresto del server...{Style.RESET_ALL}")
                    break
                
                else:
                    print(f"{Fore.RED}Comando non valido. Comandi disponibili: list, kick <username>, log, stop{Style.RESET_ALL}")
            
            except Exception as e:
                logging.error(f"Errore nel gestore dei comandi: {str(e)}")

if __name__ == '__main__':
    server = Server()
    server.start() 