import socket
import json
import threading
from colorama import init, Fore, Style

# Inizializzazione colorama per i colori nel terminale
init()

class Client:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.username = None
        self.connected = False

    def connect(self):
        """Connette il client al server"""
        try:
            self.socket.connect((self.host, self.port))
            self.connected = True
            
            # Invia username al server
            self.username = input(f"{Fore.CYAN}Inserisci il tuo username: {Style.RESET_ALL}")
            self.socket.send(self.username.encode())
            
            # Avvia thread per ricevere i messaggi
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            print(f"{Fore.GREEN}Connesso al server!{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Comandi disponibili:{Style.RESET_ALL}")
            print("- @username messaggio: invia un messaggio privato")
            print("- broadcast messaggio: invia un messaggio a tutti")
            print("- quit: esci dal programma")
            
            self.send_messages()
            
        except Exception as e:
            print(f"{Fore.RED}Errore di connessione: {str(e)}{Style.RESET_ALL}")
            self.connected = False

    def receive_messages(self):
        """Riceve i messaggi dal server"""
        while self.connected:
            try:
                message = self.socket.recv(1024).decode()
                if not message:
                    break
                
                data = json.loads(message)
                
                if data['type'] == 'message':
                    print(f"{Fore.GREEN}{data['from']}: {data['message']}{Style.RESET_ALL}")
                elif data['type'] == 'private':
                    print(f"{Fore.MAGENTA}[PM da {data['from']}]: {data['message']}{Style.RESET_ALL}")
                elif data['type'] == 'system':
                    print(f"{Fore.YELLOW}[Sistema]: {data['message']}{Style.RESET_ALL}")
                elif data['type'] == 'error':
                    print(f"{Fore.RED}[Errore]: {data['message']}{Style.RESET_ALL}")
                
            except:
                break
        
        print(f"{Fore.RED}Disconnesso dal server{Style.RESET_ALL}")
        self.connected = False

    def send_messages(self):
        """Gestisce l'invio dei messaggi"""
        while self.connected:
            try:
                message = input(f"{Fore.CYAN}Tu: {Style.RESET_ALL}")
                
                if message.lower() == 'quit':
                    break
                
                if message.startswith('@'):
                    # Messaggio privato
                    parts = message[1:].split(' ', 1)
                    if len(parts) == 2:
                        recipient, content = parts
                        data = {
                            'type': 'private',
                            'to': recipient,
                            'message': content
                        }
                        self.socket.send(json.dumps(data).encode())
                    else:
                        print(f"{Fore.RED}Formato non valido. Usa: @username messaggio{Style.RESET_ALL}")
                
                elif message.startswith('broadcast '):
                    # Messaggio broadcast
                    content = message[9:]
                    data = {
                        'type': 'broadcast',
                        'message': content
                    }
                    self.socket.send(json.dumps(data).encode())
                
                else:
                    print(f"{Fore.RED}Comando non valido{Style.RESET_ALL}")
                
            except Exception as e:
                print(f"{Fore.RED}Errore nell'invio del messaggio: {str(e)}{Style.RESET_ALL}")
                break
        
        self.disconnect()

    def disconnect(self):
        """Disconnette il client dal server"""
        self.connected = False
        self.socket.close()

if __name__ == '__main__':
    client = Client(host='localhost', port=5000)
    client.connect() 