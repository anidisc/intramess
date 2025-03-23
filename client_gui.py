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
            
            # Richiedi lista utenti
            self.request_user_list()
            
            # Avvia thread ricezione
            self.running = True
            self.receiver_thread = threading.Thread(target=self.receive_messages)
            self.receiver_thread.daemon = True
            self.receiver_thread.start()
            
            return True
        except Exception as e:
            print(f"Errore connessione: {e}")
            return False

    def request_user_list(self):
        if self.socket:
            try:
                self.socket.send(json.dumps({
                    'type': 'request_users'
                }).encode() + b'\n')
            except Exception as e:
                print(f"Errore richiesta lista utenti: {e}")

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
        
        # Layout principale orizzontale
        main_layout = QHBoxLayout(central_widget)
        
        # Layout sinistro per chat e input
        left_layout = QVBoxLayout()
        
        # Area connessione
        conn_layout = QHBoxLayout()
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('Username')
        self.connect_btn = QPushButton('Connetti')
        conn_layout.addWidget(self.username_input)
        conn_layout.addWidget(self.connect_btn)
        left_layout.addLayout(conn_layout)

        # Area gruppo
        group_layout = QHBoxLayout()
        self.group_combo = QComboBox()
        self.group_combo.addItem('ALL')
        self.group_combo.setEnabled(False)
        group_layout.addWidget(QLabel('Gruppo attivo:'))
        group_layout.addWidget(self.group_combo)
        left_layout.addLayout(group_layout)

        # Aggiungiamo un tab widget per separare chat e task
        self.tab_widget = QTabWidget()
        left_layout.addWidget(self.tab_widget)
        
        # Tab Chat
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        chat_layout.addWidget(self.chat_area)

        # Area input messaggio
        msg_layout = QHBoxLayout()
        self.writing_label = QLabel('Scrivi in: ALL')
        self.message_input = QLineEdit()
        self.send_btn = QPushButton('Invia')
        msg_layout.addWidget(self.writing_label)
        msg_layout.addWidget(self.message_input)
        msg_layout.addWidget(self.send_btn)
        chat_layout.addLayout(msg_layout)

        self.tab_widget.addTab(chat_widget, "Chat")
        
        # Tab Task
        task_widget = QWidget()
        task_layout = QVBoxLayout(task_widget)
        
        # Layout superiore per creazione task
        create_task_layout = QHBoxLayout()
        self.task_group_combo = QComboBox()
        # Inizialmente aggiungiamo solo ALL, verrà aggiornato quando riceviamo la lista gruppi
        self.task_group_combo.addItem('ALL')
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Inserisci nuovo task...")
        self.create_task_btn = QPushButton("Crea Task")
        create_task_layout.addWidget(QLabel("Gruppo:"))
        create_task_layout.addWidget(self.task_group_combo)
        create_task_layout.addWidget(self.task_input)
        create_task_layout.addWidget(self.create_task_btn)
        task_layout.addLayout(create_task_layout)
        
        # Lista dei task con stile
        self.task_list = QTreeWidget()
        self.task_list.setHeaderLabels(["Task", "Gruppo", "Creato da", "Data", "Stato"])
        self.task_list.setAlternatingRowColors(True)
        self.task_list.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 11pt;
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #eee;
            }
            QTreeWidget::item:alternate {
                background-color: #f8f8f8;
            }
            QTreeWidget::item:hover {
                background-color: #e6f3ff;
            }
            QTreeWidget QHeaderView::section {
                background-color: #f0f0f0;
                padding: 6px;
                border: 1px solid #ccc;
                font-weight: bold;
            }
        """)
        task_layout.addWidget(self.task_list)
        
        self.tab_widget.addTab(task_widget, "Task")

        # Layout destro per lista utenti
        right_layout = QVBoxLayout()
        
        # Label utenti online
        users_label = QLabel('Utenti Online:')
        right_layout.addWidget(users_label)
        
        # Lista utenti
        self.users_list = QListWidget()
        self.users_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.users_list.customContextMenuRequested.connect(self.show_user_context_menu)
        right_layout.addWidget(self.users_list)

        # Aggiungi i layout al layout principale
        main_layout.addLayout(left_layout, stretch=7)  # 70% dello spazio
        main_layout.addLayout(right_layout, stretch=3)  # 30% dello spazio

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
        
        self.users_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                color: black;
                font-size: 11pt;
                padding: 5px;
            }
        """)

    def setup_signals(self):
        self.connect_btn.clicked.connect(self.handle_connection)
        self.send_btn.clicked.connect(self.send_message)
        self.message_input.returnPressed.connect(self.send_message)
        
        self.client.signals.message_received.connect(self.handle_message)
        self.client.signals.connection_lost.connect(self.handle_disconnection)
        self.client.signals.user_list_updated.connect(self.update_users_list)
        self.group_combo.currentTextChanged.connect(self.change_group)
        self.users_list.itemDoubleClicked.connect(self.start_private_chat)
        self.create_task_btn.clicked.connect(self.create_task)
        self.task_list.itemChanged.connect(self.handle_task_status_change)

    def handle_connection(self):
        if self.client.socket:
            self.client.disconnect()
            self.connect_btn.setText('Connetti')
            self.username_input.setEnabled(True)
            self.group_combo.setEnabled(False)  # Disabilita il combo box alla disconnessione
            self.group_combo.clear()
            self.group_combo.addItem('ALL')
            self.current_group = 'ALL'
            self.writing_label.setText('Scrivi in: ALL')
            self.chat_area.append('<i>Disconnesso dal server</i>')
        else:
            username = self.username_input.text().strip()
            if username:
                if self.client.connect_to_server('localhost', 5000, username):
                    self.connect_btn.setText('Disconnetti')
                    self.username_input.setEnabled(False)
                    # Il combo box verrà abilitato quando riceviamo la conferma della connessione
                else:
                    self.chat_area.append('<span style="color: red">Errore di connessione</span>')

    def handle_message(self, data):
        try:
            print(f"DEBUG GUI - Gestione messaggio: {data}")
            if data['type'] == 'connection_accepted':
                # Abilita il combo box e popola i gruppi
                self.group_combo.setEnabled(True)
                self.group_combo.clear()
                self.group_combo.addItems(data['groups'])
                # Aggiorna anche il combo box dei task
                self.task_group_combo.clear()
                self.task_group_combo.addItems(data['groups'])
                self.chat_area.append('<i style="color: green">Connesso al server</i>')
                
            elif data['type'] == 'message':
                sender = data.get('from', 'Unknown')
                message = data.get('message', '')
                group = data.get('group', 'ALL')
                group_info = f" → {group}" if group != 'ALL' else ""
                self.chat_area.append(f'<b>{sender}{group_info}</b>: {message}')
            
            elif data['type'] == 'private':
                sender = data.get('from', '')
                to = data.get('to', '')
                if sender:
                    self.chat_area.append(f'<i style="color: purple"><b>PM da {sender}</b>: {data["message"]}</i>')
                else:
                    self.chat_area.append(f'<i style="color: purple"><b>PM a {to}</b>: {data["message"]}</i>')
            
            elif data['type'] == 'system':
                self.chat_area.append(f'<i style="color: gray">{data["message"]}</i>')
            
            elif data['type'] == 'error':
                self.chat_area.append(f'<span style="color: red"><i>{data["message"]}</i></span>')
            
            elif data['type'] == 'user_list':
                self.update_users_list(data.get('users', []))
            
            elif data['type'] == 'task_list':
                print(f"DEBUG: Ricevuto aggiornamento task: {data['tasks']}")  # Debug
                self.update_task_list(data['tasks'])
            
            self.chat_area.verticalScrollBar().setValue(
                self.chat_area.verticalScrollBar().maximum()
            )
            QApplication.processEvents()
            
        except Exception as e:
            print(f"Errore gestione messaggio: {e}")

    def send_message(self):
        message = self.message_input.text().strip()
        if message and self.client.socket:
            if message.startswith('@'):
                # Controlla se è un messaggio privato o di gruppo
                parts = message[1:].split(' ', 1)
                if len(parts) == 2:
                    target, msg = parts
                    # Verifica se il target è uno username (rimuovi eventuali [gruppo])
                    target = target.split('[')[0].strip()
                    
                    # Controlla se il target è un utente nella lista
                    users_in_list = [self.users_list.item(i).text().split('[')[0].strip() 
                                   for i in range(self.users_list.count())]
                    
                    if target in users_in_list:
                        # Messaggio privato
                        data = {
                            'type': 'private_message',
                            'to': target,
                            'message': msg
                        }
                    else:
                        # Messaggio di gruppo
                        data = {
                            'type': 'group_message',
                            'group': target.upper(),
                            'message': msg
                        }
                else:
                    return
            else:
                # Messaggio nel gruppo corrente
                data = {
                    'type': 'group_message',
                    'group': self.current_group,
                    'message': message
                }
            
            print(f"DEBUG: Invio messaggio: {data}")  # Debug
            self.client.send_message(data)
            self.message_input.clear()

    def handle_disconnection(self):
        self.connect_btn.setText('Connetti')
        self.username_input.setEnabled(True)
        self.group_combo.setEnabled(False)  # Disabilita il combo box alla disconnessione
        self.group_combo.clear()
        self.group_combo.addItem('ALL')
        self.current_group = 'ALL'
        self.writing_label.setText('Scrivi in: ALL')
        self.chat_area.append('<i>Connessione persa</i>')
        self.client.socket = None

    def change_group(self, group):
        if group and group != self.current_group:
            print(f"DEBUG: Cambio gruppo da {self.current_group} a {group}")  # Debug
            self.client.send_message({
                'type': 'join_group',
                'group': group
            })
            self.current_group = group
            self.writing_label.setText(f'Scrivi in: {group}')

    def show_user_context_menu(self, position):
        menu = QMenu()
        item = self.users_list.itemAt(position)
        
        if item:
            # Estrai il nome utente dalla stringa (rimuovi il gruppo se presente)
            username = item.text().split('[')[0].strip()
            
            if username != self.client.username:
                private_msg_action = menu.addAction(f"Messaggio privato a {username}")
                action = menu.exec_(self.users_list.mapToGlobal(position))
                
                if action == private_msg_action:
                    self.start_private_chat(item)

    def start_private_chat(self, item):
        if isinstance(item, str):
            username = item
        else:
            # Se riceviamo un QListWidgetItem, estraiamo lo username
            username = item.text().split('[')[0].strip()
        
        if username != self.client.username:
            current_text = self.message_input.text()
            self.message_input.setText(f"@{username} {current_text}")
            self.message_input.setFocus()

    def update_users_list(self, users_data):
        print(f"DEBUG: Aggiornamento lista utenti: {users_data}")  # Debug
        self.users_list.clear()
        
        # Ordina gli utenti alfabeticamente
        sorted_users = sorted(users_data.items(), key=lambda x: x[0])
        
        for username, user_info in sorted_users:
            # Crea l'item con il nome utente e il suo gruppo
            display_text = f"{username}"
            if user_info['group'] != 'ALL':
                display_text += f" [{user_info['group']}]"
            
            item = QListWidgetItem(display_text)
            
            # Stile per l'utente corrente
            if username == self.client.username:
                item.setForeground(QColor('blue'))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            
            # Colore diverso per utenti in gruppi diversi da ALL
            elif user_info['group'] != 'ALL':
                item.setForeground(QColor('green'))
            
            self.users_list.addItem(item)

    def closeEvent(self, event):
        self.client.disconnect()
        event.accept()

    def create_task(self):
        task_text = self.task_input.text().strip()
        group = self.task_group_combo.currentText()
        
        if task_text and group and group != self.current_group and group != 'ALL':
            print(f"DEBUG: Creazione task: {task_text} per gruppo {group}")  # Debug
            data = {
                'type': 'create_task',
                'group': group,
                'text': task_text
            }
            self.client.send_message(data)
            self.task_input.clear()

    def handle_task_status_change(self, item, column):
        if column == 4:  # Colonna stato
            task_data = item.data(0, Qt.UserRole)
            if task_data:
                task_id = task_data['id']
                group = task_data['group']
                
                # Verifica che l'utente sia nel gruppo corretto
                if group == self.current_group:
                    is_checked = item.checkState(4) == Qt.Checked
                    data = {
                        'type': 'update_task',
                        'task_id': task_id,
                        'completed': is_checked
                    }
                    print(f"DEBUG: Invio aggiornamento task: {data}")  # Debug
                    self.client.send_message(data)
                else:
                    # Ripristina lo stato precedente se l'utente non ha i permessi
                    item.setCheckState(4, Qt.Checked if task_data['completed'] else Qt.Unchecked)

    def update_task_list(self, tasks):
        print(f"DEBUG: Aggiornamento lista task nella GUI")
        self.task_list.clear()
        
        for task in tasks:
            item = QTreeWidgetItem()
            
            # Crea il testo del task con stile HTML e ID
            task_text = f"#{task['id']} - {task['text']}"
            
            if task['completed']:
                item.setText(0, f"✓ {task_text} (Completato da {task['completed_by']} il {task['completed_date']})")
                item.setForeground(0, QColor('#666666'))
                font = item.font(0)
                font.setStrikeOut(True)
                item.setFont(0, font)
            else:
                item.setText(0, task_text)
                item.setForeground(0, QColor('#000000'))
            
            # Imposta gli altri campi
            item.setText(1, task['group'])
            item.setText(2, task['created_by'])
            item.setText(3, task['date'])
            
            # Imposta lo stato con checkbox
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(4, Qt.Checked if task['completed'] else Qt.Unchecked)
            
            # Memorizza l'ID del task e altre info utili
            item.setData(0, Qt.UserRole, {
                'id': task['id'],
                'group': task['group'],
                'completed': task['completed']
            })
            
            # Gestisci i permessi per la checkbox
            can_modify = task['group'] == self.current_group
            if not can_modify:
                item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            
            # Imposta stili
            if task['group'] == self.current_group:
                item.setBackground(1, QColor('#e6f3ff'))
            
            self.task_list.addTopLevelItem(item)
        
        # Adatta le colonne al contenuto
        for i in range(5):
            self.task_list.resizeColumnToContents(i)

def main():
    app = QApplication([])
    window = ChatWindow()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main() 