import sys
import json
import socket
import threading
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLineEdit, QTextEdit, 
                            QListWidget, QLabel, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QIcon

class ChatSignals(QObject):
    message_received = pyqtSignal(dict)
    connection_lost = pyqtSignal()
    user_list_updated = pyqtSignal(list)

class ChatClient:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.username = None
        self.signals = ChatSignals()

    def connect_to_server(self, host='localhost', port=5000, username=''):
        try:
            self.socket.connect((host, port))
            self.connected = True
            self.username = username
            self.socket.send(username.encode())
            
            # Avvia thread per ricevere i messaggi
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            return True
        except Exception as e:
            return False

    def receive_messages(self):
        while self.connected:
            try:
                message = self.socket.recv(1024).decode()
                if not message:
                    break
                
                data = json.loads(message)
                self.signals.message_received.emit(data)
                
            except:
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
        self.connected = False
        try:
            self.socket.close()
        except:
            pass

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.client = ChatClient()
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

        # Lista utenti
        users_label = QLabel('Utenti Online')
        users_label.setStyleSheet('font-weight: bold; color: #333;')
        left_layout.addWidget(users_label)
        
        self.users_list = QListWidget()
        self.users_list.setStyleSheet("""
            QListWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
        """)
        left_layout.addWidget(self.users_list)
        
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
            }
        """)
        right_layout.addWidget(self.chat_area)

        # Area input
        input_layout = QHBoxLayout()
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText('Scrivi un messaggio...')
        self.message_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
        """)
        input_layout.addWidget(self.message_input)

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
        self.message_input.returnPressed.connect(self.send_message)
        
        # Segnali del client
        self.client.signals.message_received.connect(self.handle_message)
        self.client.signals.connection_lost.connect(self.handle_disconnection)

    def handle_connection(self):
        if not self.client.connected:
            username, ok = QInputDialog.getText(self, 'Connessione', 'Inserisci il tuo username:')
            if ok and username:
                if self.client.connect_to_server(username=username):
                    self.connect_btn.setText('Disconnetti')
                    self.send_btn.setEnabled(True)
                    self.chat_area.append('<b>Connesso al server!</b>')
                else:
                    QMessageBox.critical(self, 'Errore', 'Impossibile connettersi al server')
        else:
            self.client.disconnect()
            self.connect_btn.setText('Connetti')
            self.send_btn.setEnabled(False)
            self.users_list.clear()
            self.chat_area.append('<b>Disconnesso dal server</b>')

    def handle_message(self, data):
        if data['type'] == 'message':
            self.chat_area.append(f'<b>{data["from"]}</b>: {data["message"]}')
        elif data['type'] == 'private':
            self.chat_area.append(f'<b><i>PM da {data["from"]}</i></b>: {data["message"]}')
        elif data['type'] == 'system':
            self.chat_area.append(f'<i>{data["message"]}</i>')
        elif data['type'] == 'error':
            self.chat_area.append(f'<span style="color: red"><i>{data["message"]}</i></span>')

    def handle_disconnection(self):
        self.connect_btn.setText('Connetti')
        self.send_btn.setEnabled(False)
        self.users_list.clear()
        QMessageBox.warning(self, 'Disconnesso', 'La connessione con il server è stata persa')

    def send_message(self):
        message = self.message_input.text().strip()
        if not message:
            return
        
        if message.startswith('@'):
            # Messaggio privato
            parts = message[1:].split(' ', 1)
            if len(parts) == 2:
                recipient, content = parts
                self.client.send_message('private', to=recipient, message=content)
            else:
                self.chat_area.append('<span style="color: red"><i>Formato non valido. Usa: @username messaggio</i></span>')
        else:
            # Messaggio broadcast
            self.client.send_message('broadcast', message=message)
        
        self.message_input.clear()

def main():
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 