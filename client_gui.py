import sys
import json
import socket
import threading
import hashlib
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLineEdit, QTextEdit, 
                            QListWidget, QLabel, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QIcon, QColor

class ChatSignals(QObject):
    message_received = pyqtSignal(dict)
    connection_lost = pyqtSignal()
    user_list_updated = pyqtSignal(list)
    username_response = pyqtSignal(bool, str)

class ChatClient:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.username = None
        self.signals = ChatSignals()

    def connect_to_server(self, host='localhost', port=5000, username=''):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            
            # Invia username e attendi risposta
            self.socket.send(username.encode())
            
            # Leggi la risposta del server con un timeout
            self.socket.settimeout(5.0)  # 5 secondi di timeout
            try:
                response = json.loads(self.socket.recv(1024).decode())
                self.socket.settimeout(None)  # Rimuovi il timeout dopo la risposta iniziale
                
                if response['type'] == 'username_taken':
                    self.signals.username_response.emit(False, response['message'])
                    self.socket.close()
                    return False
                elif response['type'] == 'username_accepted':
                    self.connected = True
                    self.username = username
                    
                    # Avvia thread per ricevere i messaggi
                    receive_thread = threading.Thread(target=self.receive_messages)
                    receive_thread.daemon = True
                    receive_thread.start()
                    
                    self.signals.username_response.emit(True, "Username accettato")
                    return True
                else:
                    self.signals.username_response.emit(False, "Risposta non valida dal server")
                    self.socket.close()
                    return False
            
            except socket.timeout:
                self.signals.username_response.emit(False, "Timeout nella risposta del server")
                self.socket.close()
                return False
            except json.JSONDecodeError:
                self.signals.username_response.emit(False, "Risposta non valida dal server")
                self.socket.close()
                return False
            
        except Exception as e:
            self.signals.username_response.emit(False, str(e))
            try:
                self.socket.close()
            except:
                pass
            return False

    def receive_messages(self):
        """Riceve i messaggi dal server"""
        while self.connected:
            try:
                message = self.socket.recv(1024).decode()
                if not message:
                    break
                
                try:
                    data = json.loads(message)
                    self.signals.message_received.emit(data)
                    
                    # Aggiorna la lista utenti se il server la invia
                    if data['type'] == 'user_list':
                        self.signals.user_list_updated.emit(data['users'])
                except json.JSONDecodeError:
                    continue
                
            except Exception as e:
                break
        
        self.connected = False
        self.signals.connection_lost.emit()

    def send_message(self, message_type, **kwargs):
        if not self.connected:
            return False
        
        try:
            data = {'type': message_type, **kwargs}
            self.socket.send(json.dumps(data).encode())
            return True
        except:
            return False

    def disconnect(self):
        if self.connected:
            try:
                # Invia messaggio di disconnessione al server
                self.socket.send(json.dumps({
                    'type': 'disconnect',
                    'message': 'Client disconnesso'
                }).encode())
            except:
                pass
        self.connected = False
        try:
            self.socket.close()
        except:
            pass

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.client = ChatClient()
        self.user_colors = {}
        self.init_ui()
        self.setup_signals()

    def init_ui(self):
        self.setWindowTitle('IntraMessenger')
        self.setMinimumSize(800, 600)

        # Widget principale
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Pannello sinistro (lista utenti e controlli)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Pulsante di connessione
        self.connect_btn = QPushButton('Connetti')
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        left_layout.addWidget(self.connect_btn)

        # Username label
        self.username_label = QLabel('')
        self.username_label.setStyleSheet("""
            QLabel {
                color: #007bff;
                padding: 8px;
                background-color: #e9ecef;
                border: 2px solid #007bff;
                border-radius: 4px;
                margin: 8px 0;
                font-weight: bold;
                font-size: 14px;
                text-align: center;
            }
        """)
        self.username_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.username_label)

        # Separatore
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #dee2e6;")
        left_layout.addWidget(separator)

        # Header lista utenti con pulsante refresh
        users_header = QHBoxLayout()
        users_label = QLabel('Utenti Online')
        users_label.setStyleSheet('font-weight: bold; color: #333;')
        users_header.addWidget(users_label)
        
        self.refresh_btn = QPushButton('🔄')
        self.refresh_btn.setToolTip('Aggiorna lista utenti')
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        self.refresh_btn.clicked.connect(self.request_users_list)
        users_header.addWidget(self.refresh_btn)
        left_layout.addLayout(users_header)

        # Lista utenti
        self.users_list = QListWidget()
        self.users_list.setStyleSheet("""
            QListWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:selected {
                background-color: #007bff;
                color: white;
            }
        """)
        left_layout.addWidget(self.users_list)
        
        # Aggiungi doppio click sulla lista utenti
        self.users_list.itemDoubleClicked.connect(self.start_private_message)
        
        layout.addWidget(left_panel, 1)

        # Pannello destro (chat)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Area messaggi
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        right_layout.addWidget(self.chat_area)

        # Area input
        input_layout = QHBoxLayout()
        
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText('Scrivi un messaggio... (Shift+Invio per andare a capo)')
        self.message_input.setMaximumHeight(100)  # Altezza massima
        self.message_input.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-size: 16px;
                line-height: 1.4;
            }
        """)
        input_layout.addWidget(self.message_input)

        # Gestiamo l'evento keyPressEvent del QTextEdit
        self.message_input.keyPressEvent = self.handle_input_keypress

        self.send_btn = QPushButton('Invia')
        self.send_btn.setEnabled(False)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        input_layout.addWidget(self.send_btn)
        
        right_layout.addLayout(input_layout)
        layout.addWidget(right_panel, 3)

        # Stile generale della finestra
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f2f5;
            }
        """)

    def setup_signals(self):
        # Connessione pulsanti
        self.connect_btn.clicked.connect(self.handle_connection)
        self.send_btn.clicked.connect(self.send_message)
        self.message_input.keyPressEvent = self.handle_input_keypress
        
        # Segnali del client
        self.client.signals.message_received.connect(self.handle_message)
        self.client.signals.connection_lost.connect(self.handle_disconnection)
        self.client.signals.user_list_updated.connect(self.update_users_list)
        self.client.signals.username_response.connect(self.handle_username_response)

    def handle_connection(self):
        if not self.client.connected:
            self.try_connect()
        else:
            self.client.disconnect()
            self.connect_btn.setText('Connetti')
            self.send_btn.setEnabled(False)
            self.users_list.clear()
            self.username_label.setText('')
            self.chat_area.append('<b>Disconnesso dal server</b>')

    def try_connect(self):
        """Gestisce il tentativo di connessione e la verifica dell'username"""
        username, ok = QInputDialog.getText(self, 'Connessione', 'Inserisci il tuo username:')
        if ok and username:
            self.client.connect_to_server(username=username)

    def handle_username_response(self, accepted, message):
        """Gestisce la risposta del server alla richiesta di username"""
        if accepted:
            self.connect_btn.setText('Disconnetti')
            self.send_btn.setEnabled(True)
            self.chat_area.append('<b>Connesso al server!</b>')
            # Aggiorna la label con l'username in modo più evidente
            self.username_label.setText(f'👤 {self.client.username}')
            
            # Richiedi esplicitamente la lista degli utenti
            self.client.send_message('request_users')
        else:
            QMessageBox.critical(self, 'Errore', f'Impossibile connettersi: {message}')
            self.try_connect()

    def handle_message(self, data):
        if data['type'] == 'server_shutdown':
            self.chat_area.append(f'<span style="color: red"><b>{data["message"]}</b></span>')
            self.client.disconnect()
            self.connect_btn.setText('Connetti')
            self.send_btn.setEnabled(False)
            self.users_list.clear()
            self.username_label.setText('')
            QMessageBox.warning(self, 'Server Disconnesso', 'Il server è stato arrestato')
        elif data['type'] == 'user_list':
            self.update_users_list(data['users'])
        elif data['type'] == 'message':
            color = self.get_user_color(data['from'])
            formatted_message = data['message'].replace('\n', '<br>')
            self.chat_area.append(f'<b style="color: {color}">{data["from"]}</b>: {formatted_message}')
        elif data['type'] == 'private':
            color = self.get_user_color(data['from'])
            formatted_message = data['message'].replace('\n', '<br>')
            self.chat_area.append(f'<b style="color: {color}"><i>PM da {data["from"]}</i></b>: {formatted_message}')
        elif data['type'] == 'system':
            self.chat_area.append(f'<i style="color: #666666">{data["message"]}</i>')
            # Richiedi la lista utenti aggiornata dopo ogni messaggio di sistema
            self.client.send_message('request_users')
        elif data['type'] == 'error':
            self.chat_area.append(f'<span style="color: red"><i>{data["message"]}</i></span>')

    def handle_disconnection(self):
        self.connect_btn.setText('Connetti')
        self.send_btn.setEnabled(False)
        self.users_list.clear()
        # Pulisci la label dell'username
        self.username_label.setText('')
        QMessageBox.warning(self, 'Disconnesso', 'La connessione con il server è stata persa')

    def update_users_list(self, users):
        self.users_list.clear()
        for user in users:
            if user != self.client.username:  # Non mostrare l'utente corrente nella lista
                item = self.users_list.addItem(user)
                # Aggiorna il colore dell'utente nella lista
                color = self.get_user_color(user)
                self.users_list.item(self.users_list.count() - 1).setForeground(QColor(color))
        
        # Aggiorna la GUI
        QApplication.processEvents()

    def start_private_message(self, item):
        """Avvia un messaggio privato quando si fa doppio click su un utente"""
        self.message_input.setText(f'@{item.text()} ')
        self.message_input.setFocus()

    def handle_input_keypress(self, event):
        """Gestisce gli eventi della tastiera nell'input dei messaggi"""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                # Shift+Enter: inserisce una nuova riga
                self.message_input.insertPlainText('\n')
            else:
                # Solo Enter: invia il messaggio
                self.send_message()
        else:
            # Per tutti gli altri tasti, usa il comportamento predefinito
            QTextEdit.keyPressEvent(self.message_input, event)

    def send_message(self):
        message = self.message_input.toPlainText().strip()
        if not message:
            return
        
        if message.startswith('@'):
            # Messaggio privato
            parts = message.split(' ', 1)
            if len(parts) == 2:
                recipient = parts[0][1:]
                content = parts[1]
                self.client.send_message('private', to=recipient, message=content)
                # Mostra il messaggio inviato nella chat
                color = self.get_user_color(self.client.username)
                self.chat_area.append(f'<b style="color: {color}"><i>PM a {recipient}</i></b>: {content}')
            else:
                self.chat_area.append('<span style="color: red"><i>Formato non valido. Usa: @username messaggio</i></span>')
        else:
            # Messaggio broadcast
            self.client.send_message('broadcast', message=message)
            # Mostra il messaggio inviato nella chat preservando la formattazione
            color = self.get_user_color(self.client.username)
            formatted_message = message.replace('\n', '<br>')
            self.chat_area.append(f'<b style="color: {color}">Tu</b>: {formatted_message}')
        
        self.message_input.clear()
        self.message_input.setFocus()

    def request_users_list(self):
        """Richiede la lista aggiornata degli utenti al server"""
        if self.client.connected:
            self.client.send_message('request_users')

    def get_user_color(self, username):
        """Genera un colore unico per ogni utente basato sul suo username"""
        if username not in self.user_colors:
            # Usa l'hash dell'username per generare un colore
            hash_obj = hashlib.md5(username.encode())
            hash_hex = hash_obj.hexdigest()
            
            # Genera colori più scuri per una migliore leggibilità
            r = int(hash_hex[:2], 16) % 156  # Massimo 156 per evitare colori troppo chiari
            g = int(hash_hex[2:4], 16) % 156
            b = int(hash_hex[4:6], 16) % 156
            
            # Assicurati che almeno una componente sia sufficientemente scura
            if max(r, g, b) < 50:
                max_component = max(r, g, b)
                if max_component == r: r = 100
                elif max_component == g: g = 100
                else: b = 100
            
            self.user_colors[username] = f"#{r:02x}{g:02x}{b:02x}"
        
        return self.user_colors[username]

def main():
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 