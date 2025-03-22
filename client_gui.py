from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import socket
import json
import threading
import hashlib

class ChatSignals(QObject):
    message_received = pyqtSignal(dict)
    connection_lost = pyqtSignal()
    user_list_updated = pyqtSignal(list)
    username_response = pyqtSignal(dict)

class ChatClient(QObject):
    def __init__(self):
        super().__init__()
        self.socket = None
        self.running = False
        self.username = None
        self.signals = ChatSignals()

    def connect_to_server(self, host, port, username):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.username = username
            
            # Invia username
            self.socket.send(username.encode())
            
            # Ricevi risposta iniziale
            response = json.loads(self.socket.recv(4096).decode())
            if response.get('type') == 'error':
                self.socket.close()
                self.socket = None
                self.signals.message_received.emit(response)
                return False
                
            self.signals.message_received.emit(response)
            
            # Avvia thread ricezione
            self.running = True
            self.receiver_thread = threading.Thread(target=self.receive_messages)
            self.receiver_thread.daemon = True
            self.receiver_thread.start()
            
            return True
        except Exception as e:
            print(f"Errore connessione: {e}")
            return False

    def receive_messages(self):
        while self.running and self.socket:
            try:
                data = self.socket.recv(4096).decode()
                if not data:
                    break
                    
                messages = data.split('\n')
                for message in messages:
                    if message:
                        try:
                            msg_data = json.loads(message)
                            print(f"DEBUG Client - Messaggio ricevuto: {msg_data}")
                            self.signals.message_received.emit(msg_data)
                        except json.JSONDecodeError as e:
                            print(f"Errore decodifica JSON: {e}")
                            continue
                
            except Exception as e:
                print(f"Errore ricezione: {e}")
                break
                
        self.running = False
        self.signals.connection_lost.emit()

    def send_message(self, message):
        if self.socket:
            try:
                # Aggiungi newline come delimitatore
                self.socket.send((json.dumps(message) + '\n').encode())
            except Exception as e:
                print(f"Errore invio: {e}")

    def disconnect(self):
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.client = ChatClient()
        self.current_group = 'ALL'
        self.init_ui()
        self.setup_signals()

    def init_ui(self):
        self.setWindowTitle('Chat Client')
        self.setGeometry(100, 100, 800, 600)

        # Widget centrale
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Area connessione
        conn_layout = QHBoxLayout()
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('Username')
        self.connect_btn = QPushButton('Connetti')
        conn_layout.addWidget(self.username_input)
        conn_layout.addWidget(self.connect_btn)
        layout.addLayout(conn_layout)

        # Area gruppo
        group_layout = QHBoxLayout()
        self.group_combo = QComboBox()
        self.group_combo.addItem('ALL')
        self.group_combo.setEnabled(False)
        group_layout.addWidget(QLabel('Gruppo attivo:'))
        group_layout.addWidget(self.group_combo)
        layout.addLayout(group_layout)

        # Area chat
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        layout.addWidget(self.chat_area)

        # Area input messaggio
        msg_layout = QHBoxLayout()
        self.writing_label = QLabel('Scrivi in: ALL')
        self.message_input = QLineEdit()
        self.send_btn = QPushButton('Invia')
        msg_layout.addWidget(self.writing_label)
        msg_layout.addWidget(self.message_input)
        msg_layout.addWidget(self.send_btn)
        layout.addLayout(msg_layout)

        # Imposta stili
        self.chat_area.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: black;
                font-size: 12pt;
            }
        """)
        
        self.message_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                color: black;
                font-size: 12pt;
                padding: 5px;
            }
        """)

    def setup_signals(self):
        self.connect_btn.clicked.connect(self.handle_connection)
        self.send_btn.clicked.connect(self.send_message)
        self.message_input.returnPressed.connect(self.send_message)
        
        self.client.signals.message_received.connect(self.handle_message)
        self.client.signals.connection_lost.connect(self.handle_disconnection)
        self.group_combo.currentTextChanged.connect(self.change_group)

    def handle_connection(self):
        if self.client.socket:
            self.client.disconnect()
            self.connect_btn.setText('Connetti')
            self.username_input.setEnabled(True)
            self.chat_area.append('<i>Disconnesso dal server</i>')
        else:
            username = self.username_input.text().strip()
            if username:
                if self.client.connect_to_server('localhost', 5000, username):
                    self.connect_btn.setText('Disconnetti')
                    self.username_input.setEnabled(False)
                    self.chat_area.append('<i>Connesso al server</i>')
                else:
                    self.chat_area.append('<span style="color: red">Errore di connessione</span>')

    def handle_message(self, data):
        try:
            print(f"DEBUG GUI - Gestione messaggio: {data}")
            if data['type'] == 'message':
                sender = data.get('from', 'Unknown')
                message = data.get('message', '')
                group = data.get('group', 'ALL')
                group_info = f" → {group}" if group != 'ALL' else ""
                self.chat_area.append(f'<b>{sender}{group_info}</b>: {message}')
            elif data['type'] == 'system':
                self.chat_area.append(f'<i>{data["message"]}</i>')
            elif data['type'] == 'connection_accepted':
                self.group_combo.clear()
                self.group_combo.addItems(data['groups'])
                self.group_combo.setEnabled(True)
            
            self.chat_area.verticalScrollBar().setValue(
                self.chat_area.verticalScrollBar().maximum()
            )
        except Exception as e:
            print(f"Errore gestione messaggio: {e}")

    def send_message(self):
        message = self.message_input.text().strip()
        if message and self.client.socket:
            if message.startswith('@ALL '):  # Forza invio al gruppo ALL
                msg = message[5:]
                data = {
                    'type': 'group_message',
                    'group': 'ALL',
                    'message': msg
                }
            else:  # Invia al gruppo corrente
                data = {
                    'type': 'group_message',
                    'group': self.current_group,
                    'message': message
                }
            self.client.send_message(data)
            self.message_input.clear()

    def handle_disconnection(self):
        self.connect_btn.setText('Connetti')
        self.username_input.setEnabled(True)
        self.chat_area.append('<i>Connessione persa</i>')
        self.client.socket = None

    def change_group(self, group):
        if group != self.current_group:
            self.client.send_message({
                'type': 'join_group',
                'group': group
            })
            self.current_group = group
            self.writing_label.setText(f'Scrivi in: {group}')

    def closeEvent(self, event):
        self.client.disconnect()
        event.accept()

def main():
    app = QApplication([])
    window = ChatWindow()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main() 