from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import socket
import json
import threading
import hashlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os
import subprocess
import platform
from datetime import datetime
from PyQt5.QtCore import QTimer
from login_dialog import LoginDialog
from signup_dialog import SignupDialog
from database import Database

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
        self.config = self.load_config()

    def load_config(self):
        """Carica la configurazione dal file config.json"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Errore nel caricamento della configurazione: {e}")
            # Configurazione di default
            return {
                "server": {
                    "host": "localhost",
                    "port": 5000
                },
                "client": {
                    "window": {
                        "width": 800,
                        "height": 600,
                        "title": "Chat Client"
                    },
                    "chat": {
                        "message_height": 60,
                        "min_task_width": 300
                    }
                }
            }

    def connect_to_server(self, host, port, credentials):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            
            # Invia credenziali di login
            self.socket.send(json.dumps({
                'type': 'login',
                'username': credentials['username'],
                'password': credentials['password']
            }).encode())
            
            # Ricevi risposta iniziale
            response = json.loads(self.socket.recv(4096).decode())
            if response.get('type') == 'error':
                self.socket.close()
                self.socket = None
                self.signals.message_received.emit(response)
                return False
                
            self.username = credentials['username']
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
                            print(f"DEBUG Client - Messaggio ricevuto: tipo={msg_data.get('type')}, lunghezza={len(message)} bytes")
                            
                            # Log specifico per i messaggi storici
                            if msg_data.get('type') == 'historical_messages':
                                print(f"DEBUG Client - Ricevuti messaggi storici: {len(msg_data.get('messages', {}))} gruppi")
                                for group, msgs in msg_data.get('messages', {}).items():
                                    print(f"DEBUG Client - Gruppo {group}: {len(msgs)} messaggi")
                            
                            self.signals.message_received.emit(msg_data)
                        except json.JSONDecodeError as e:
                            print(f"Errore decodifica JSON: {e}")
                            print(f"Messaggio problematico: {message[:100]}...")
                            continue
                
            except Exception as e:
                print(f"Errore ricezione: {e}")
                break
                
        self.running = False
        self.signals.connection_lost.emit()

    def send_message(self, message):
        if self.socket:
            try:
                self.socket.send(json.dumps(message).encode('utf-8'))
            except Exception as e:
                print(f"Errore invio messaggio: {e}")

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
        self.unread_messages = 0
        self.config = self.client.config
        self.init_ui()
        self.setup_signals()
        self.flash_timer = QTimer()
        self.flash_timer.timeout.connect(self.flash_tab)
        self.is_flashing = False
        self.flash_count = 0

    def init_ui(self):
        self.setWindowTitle(self.config['client']['window']['title'])
        self.setGeometry(100, 100, 
                        self.config['client']['window']['width'],
                        self.config['client']['window']['height'])

        # Widget centrale
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principale orizzontale
        main_layout = QHBoxLayout(central_widget)
        
        # Layout sinistro per chat e input
        left_layout = QVBoxLayout()
        
        # Area connessione
        conn_layout = QHBoxLayout()
        self.login_btn = QPushButton('Login')
        self.signup_btn = QPushButton('Sign Up')
        self.login_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
                min-width: 80px;
                background-color: #2ecc71;
                border: none;
                color: white;
            }
            QPushButton:hover {
                opacity: 0.8;
            }
            QPushButton:pressed {
                opacity: 1;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.signup_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
                min-width: 80px;
                background-color: #3498db;
                border: none;
                color: white;
            }
            QPushButton:hover {
                opacity: 0.8;
            }
            QPushButton:pressed {
                opacity: 1;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        conn_layout.addWidget(self.login_btn)
        conn_layout.addWidget(self.signup_btn)
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
        
        # Area chat con più spazio
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        chat_layout.addWidget(self.chat_area, stretch=7)  # Diamo più spazio alla chat

        # Area input messaggio
        msg_layout = QVBoxLayout()
        
        # Input box più compatto
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Scrivi il tuo messaggio...")
        self.message_input.setFixedHeight(self.config['client']['chat']['message_height'])
        
        # Layout orizzontale per combo box e pulsante sotto l'input
        bottom_layout = QHBoxLayout()
        
        # Label "Scrivi in" stilizzata
        self.writing_label = QLabel('Scrivi in')
        self.writing_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 12px;
                font-weight: bold;
                padding: 5px;
                margin-right: 5px;
                background-color: #ecf0f1;
                border-radius: 4px;
            }
        """)
        bottom_layout.addWidget(self.writing_label)
        
        self.writing_group_combo = QComboBox()
        self.writing_group_combo.setStyleSheet("""
            QComboBox {
                background-color: #2c3e50;
                color: white;
                border: 1px solid #34495e;
                border-radius: 4px;
                padding: 5px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }
            QComboBox QListView {
                background-color: #2c3e50;
                color: white;
                selection-background-color: #2ecc71;
                selection-color: white;
                border: 1px solid #34495e;
                border-radius: 4px;
                padding: 5px;
            }
            QComboBox QListView::item {
                padding: 5px;
                min-height: 25px;
            }
            QComboBox QListView::item:hover {
                background-color: #27ae60;
                color: white;
            }
            QComboBox QListView::item:selected {
                background-color: #2ecc71;
                color: white;
            }
        """)
        self.writing_group_combo.setView(QListView())
        self.writing_group_combo.setMinimumWidth(100)
        
        bottom_layout.addWidget(self.writing_group_combo)
        bottom_layout.addStretch()  # Aggiunge spazio elastico tra combo box e pulsante
        self.send_btn = QPushButton('Invia')
        bottom_layout.addWidget(self.send_btn)
        
        msg_layout.addWidget(self.message_input)
        msg_layout.addLayout(bottom_layout)
        chat_layout.addLayout(msg_layout, stretch=1)  # Meno spazio per l'area input

        self.chat_tab_index = self.tab_widget.addTab(chat_widget, "Chat")
        
        # Tab Task
        task_widget = QWidget()
        task_layout = QVBoxLayout(task_widget)
        
        # Aggiunta filtro gruppo
        filter_layout = QHBoxLayout()
        self.task_group_filter = QComboBox()
        self.task_group_filter.addItem("Tutti i gruppi")
        filter_layout.addWidget(QLabel("Visualizza tasks del gruppo:"))
        filter_layout.addWidget(self.task_group_filter)
        
        # Pulsante PDF
        self.pdf_btn = QPushButton("Esporta in PDF")
        self.pdf_btn.setEnabled(False)  # Sarà abilitato solo per i gruppi dell'utente
        filter_layout.addStretch()
        filter_layout.addWidget(self.pdf_btn)
        
        task_layout.addLayout(filter_layout)
        
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
        self.task_list.setHeaderLabels([
            "Stato", 
            "Task", 
            "Gruppo", 
            "Gruppo Richiedente",
            "Creato da", 
            "Data", 
            "Completato da", 
            "Data completamento"
        ])
        self.task_list.setAlternatingRowColors(True)
        self.task_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_list.customContextMenuRequested.connect(self.show_task_context_menu)
        
        # Imposta la larghezza minima della colonna Task
        self.task_list.setColumnWidth(1, self.config['client']['chat']['min_task_width'])
        
        task_layout.addWidget(self.task_list)
        
        self.task_tab_index = self.tab_widget.addTab(task_widget, "Task")

        # Layout destro per lista utenti
        right_layout = QVBoxLayout()
        
        # Label utenti online
        users_label = QLabel('Utenti Online:')
        right_layout.addWidget(users_label)
        
        # Lista utenti con larghezza fissa
        self.users_list = QListWidget()
        self.users_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.users_list.customContextMenuRequested.connect(self.show_user_context_menu)
        self.users_list.setMaximumWidth(200)  # Larghezza massima fissa
        right_layout.addWidget(self.users_list)

        # Aggiungi i layout al layout principale
        main_layout.addLayout(left_layout, stretch=8)  # 80% dello spazio
        main_layout.addLayout(right_layout, stretch=2)  # 20% dello spazio

        # Imposta stili
        self.chat_area.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: black;
                font-size: 12pt;
            }
        """)
        
        self.message_input.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: black;
                font-size: 12pt;
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                min-height: 60px;
                max-height: 60px;
            }
            
            QTextEdit:focus {
                border-color: #3498db;
                outline: none;
            }
        """)
        
        self.users_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                color: black;
                font-size: 11pt;
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #ecf0f1;
            }
            
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
        """)

        # Stile per le tab
        self.tab_widget.setStyleSheet("""
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                padding: 8px;
                margin-right: 4px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #0078d7;
                color: white;
            }
            QTabBar::tab:hover {
                background: #e6f3ff;
            }
        """)

        # Stili comuni per i pulsanti
        button_style = """
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
                min-width: 80px;
            }
            
            QPushButton:hover {
                opacity: 0.8;
            }
            
            QPushButton:pressed {
                opacity: 1;
            }
            
            QPushButton:disabled {
                background-color: #cccccc;
                border: none;
                color: #666666;
            }
        """

        # Stile per il pulsante Connetti/Disconnetti
        connect_button_style = button_style + """
            QPushButton {
                background-color: #2ecc71;
                border: none;
                color: white;
            }
            
            QPushButton[connected="true"] {
                background-color: #e74c3c;
            }
        """

        # Stile per il pulsante Invia
        send_button_style = button_style + """
            QPushButton {
                background-color: #3498db;
                border: none;
                color: white;
            }
        """

        # Stile per il pulsante Esporta PDF
        pdf_button_style = button_style + """
            QPushButton {
                background-color: #9b59b6;
                border: none;
                color: white;
            }
        """

        # Applica gli stili ai pulsanti
        self.login_btn.setStyleSheet(connect_button_style)
        self.signup_btn.setStyleSheet(connect_button_style)
        self.send_btn.setStyleSheet(send_button_style)
        self.pdf_btn.setStyleSheet(pdf_button_style)

        # Stile per i ComboBox
        combo_style = """
            QComboBox {
                padding: 6px 30px 6px 10px;  /* Più spazio a destra per la freccia */
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
                font-size: 11pt;
                min-width: 150px;
            }
            
            QComboBox:hover {
                border-color: #2ecc71;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 30px;
                background-color: #2ecc71;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            
            QComboBox::down-arrow {
                image: none;
                border-style: solid;
                border-width: 6px 5px 0 5px;
                border-color: white transparent transparent transparent;
                margin-right: 10px;
            }
            
            QComboBox QListView {
                border: 1px solid #bdc3c7;
                padding: 4px;
                background-color: white;
                outline: 0px;
                min-width: 150px;
            }
            
            QComboBox::item {
                padding: 4px;
                min-height: 25px;
            }
            
            QComboBox::item:selected {
                background-color: #2ecc71;
                color: white;
            }
            
            QComboBox::item:hover {
                background-color: #2ecc71;
                color: white;
            }
            
            QComboBox:disabled {
                background-color: #f5f5f5;
                color: #999999;
            }
        """
        
        self.group_combo.setStyleSheet(combo_style)
        self.task_group_filter.setStyleSheet(combo_style)

        # Forza l'aggiornamento dello stile
        self.group_combo.setView(QListView())
        self.task_group_filter.setView(QListView())

        # Stile per i campi di input
        input_style = """
            QLineEdit, QTextEdit {
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
                font-size: 11pt;
            }
            
            QLineEdit:focus, QTextEdit:focus {
                border-color: #3498db;
                outline: none;
            }
            
            QLineEdit:disabled {
                background-color: #f5f5f5;
                color: #999999;
            }
        """
        
        self.task_input.setStyleSheet(input_style)

        # Stile per le etichette
        label_style = """
            QLabel {
                font-size: 11pt;
                color: #2c3e50;
                padding: 4px 0;
            }
        """
        
        for label in self.findChildren(QLabel):
            label.setStyleSheet(label_style)

        # Aggiorna lo stile del QTreeWidget per i task
        self.task_list.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
                font-size: 11pt;
            }
            
            QTreeWidget::item {
                padding: 6px;
                border-bottom: 1px solid #ecf0f1;
            }
            
            QTreeWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            
            QTreeWidget::item:hover {
                background-color: #ecf0f1;
            }
            
            QTreeWidget QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
            
            QTreeWidget::indicator {
                width: 20px;
                height: 20px;
            }
            
            QTreeWidget::indicator:unchecked {
                border: 2px solid #bdc3c7;
                border-radius: 3px;
                background-color: white;
            }
            
            QTreeWidget::indicator:checked {
                border: 2px solid #2ecc71;
                border-radius: 3px;
                background-color: #2ecc71;
                image: url(checkmark.png);
            }
        """)

        # Stile per il pulsante Create Task
        create_task_style = """
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
                min-width: 100px;
                background-color: #f39c12;  /* Arancione */
                border: none;
                color: white;
            }
            
            QPushButton:hover {
                background-color: #e67e22;  /* Arancione più scuro */
                transition: background-color 0.3s;
            }
            
            QPushButton:pressed {
                background-color: #d35400;  /* Ancora più scuro quando premuto */
            }
            
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """
        
        # Applica gli stili
        self.create_task_btn.setStyleSheet(create_task_style)

        # Aggiungi il gestore del tasto per l'input del task
        self.task_input.keyPressEvent = self.handle_task_input_keypress

    def setup_signals(self):
        self.login_btn.clicked.connect(self.handle_login)
        self.signup_btn.clicked.connect(self.handle_signup)
        self.send_btn.clicked.connect(self.send_message)
        self.message_input.keyPressEvent = self.handle_message_input_keypress
        
        self.client.signals.message_received.connect(self.handle_message)
        self.client.signals.connection_lost.connect(self.handle_disconnection)
        self.client.signals.user_list_updated.connect(self.update_users_list)
        self.group_combo.currentTextChanged.connect(self.change_group)
        self.users_list.itemDoubleClicked.connect(self.start_private_chat)
        self.create_task_btn.clicked.connect(self.create_task)
        self.task_list.itemChanged.connect(self.handle_task_status_change)
        self.task_group_filter.currentTextChanged.connect(self.filter_tasks)
        self.pdf_btn.clicked.connect(self.export_to_pdf)
        self.tab_widget.currentChanged.connect(self.handle_tab_change)
        self.writing_group_combo.currentTextChanged.connect(self.change_writing_group)

    def handle_login(self):
        if self.client.socket:
            # Se siamo già connessi, disconnettiamo
            try:
                self.client.send_message({
                    'type': 'disconnect',
                    'username': self.client.username
                })
            except:
                pass
            self.client.disconnect()
            
            # Resetta l'interfaccia
            self.login_btn.setText('Login')
            self.login_btn.setStyleSheet("""
                QPushButton {
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 11pt;
                    min-width: 80px;
                    background-color: #2ecc71;
                    border: none;
                    color: white;
                }
                QPushButton:hover {
                    opacity: 0.8;
                }
                QPushButton:pressed {
                    opacity: 1;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666666;
                }
            """)
            self.login_btn.setEnabled(True)
            self.signup_btn.setEnabled(True)
            self.group_combo.setEnabled(False)
            self.group_combo.clear()
            self.group_combo.addItem('ALL')
            self.current_group = 'ALL'
            self.chat_area.append('<i>Disconnesso dal server</i>')
            
            # Pulisci la lista task
            self.task_list.clear()
            self.task_group_filter.clear()
            self.task_group_filter.addItem("Tutti i gruppi")
            
            # Pulisci la lista utenti
            self.users_list.clear()
        else:
            # Se non siamo connessi, procedi con il login
            dialog = LoginDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                credentials = dialog.get_credentials()
                if self.client.connect_to_server(
                    self.config['server']['host'],
                    self.config['server']['port'],
                    credentials
                ):
                    self.login_btn.setText('Disconnetti')
                    self.login_btn.setStyleSheet("""
                        QPushButton {
                            padding: 8px 16px;
                            border-radius: 4px;
                            font-weight: bold;
                            font-size: 11pt;
                            min-width: 80px;
                            background-color: #e74c3c;
                            border: none;
                            color: white;
                        }
                        QPushButton:hover {
                            opacity: 0.8;
                        }
                        QPushButton:pressed {
                            opacity: 1;
                        }
                        QPushButton:disabled {
                            background-color: #cccccc;
                            color: #666666;
                        }
                    """)
                    self.login_btn.setEnabled(True)
                    self.signup_btn.setEnabled(False)
                    self.chat_area.append('<i style="color: green">Login effettuato con successo</i>')
                else:
                    self.chat_area.append('<span style="color: red">Errore di login</span>')

    def handle_signup(self):
        dialog = SignupDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            credentials = dialog.get_credentials()
            try:
                # Crea una connessione diretta al database
                db = Database()
                
                # Tenta la registrazione
                success, message = db.register_user(credentials['username'], credentials['password'])
                
                if success:
                    self.chat_area.append(f'<i style="color: green">{message}</i>')
                    QMessageBox.information(self, 'Registrazione', message)
                    # Dopo la registrazione, procedi con il login
                    if self.client.connect_to_server(
                        self.config['server']['host'],
                        self.config['server']['port'],
                        credentials
                    ):
                        # Aggiorna lo stato del pulsante di login
                        self.login_btn.setText('Disconnetti')
                        self.login_btn.setStyleSheet("""
                            QPushButton {
                                padding: 8px 16px;
                                border-radius: 4px;
                                font-weight: bold;
                                font-size: 11pt;
                                min-width: 80px;
                                background-color: #e74c3c;
                                border: none;
                                color: white;
                            }
                            QPushButton:hover {
                                opacity: 0.8;
                            }
                            QPushButton:pressed {
                                opacity: 1;
                            }
                            QPushButton:disabled {
                                background-color: #cccccc;
                                color: #666666;
                            }
                        """)
                        self.login_btn.setEnabled(True)
                        self.signup_btn.setEnabled(False)
                        self.chat_area.append('<i style="color: green">Login effettuato con successo</i>')
                    else:
                        self.chat_area.append('<span style="color: red">Errore di login</span>')
                else:
                    self.chat_area.append(f'<span style="color: red">{message}</span>')
                    QMessageBox.warning(self, 'Errore Registrazione', message)
                
            except Exception as e:
                self.chat_area.append(f'<span style="color: red">Errore durante la registrazione: {str(e)}</span>')
                QMessageBox.critical(self, 'Errore', f'Errore durante la registrazione: {str(e)}')

    def handle_message(self, data):
        try:
            print(f"DEBUG GUI - Gestione messaggio: {data}")
            
            if data['type'] == 'register_response':
                if data['success']:
                    self.chat_area.append(f'<i style="color: green">{data["message"]}</i>')
                    # Mostra un messaggio di conferma nella finestra di dialogo
                    QMessageBox.information(self, 'Registrazione', data['message'])
                else:
                    self.chat_area.append(f'<span style="color: red">{data["message"]}</span>')
                    # Mostra l'errore nella finestra di dialogo
                    QMessageBox.warning(self, 'Errore Registrazione', data['message'])
                return
            
            if data['type'] == 'task_list':
                self.update_task_list(data['tasks'])
                return
            
            if self.tab_widget.currentIndex() == self.task_tab_index and data['type'] in ['message', 'private']:
                self.unread_messages += 1
                self.update_chat_tab()
                self.flash_count = 0
                self.flash_timer.start(500)
            
            if data['type'] == 'connection_accepted':
                # Abilita il combo box e popola i gruppi
                self.group_combo.setEnabled(True)
                self.group_combo.clear()
                self.group_combo.addItems(data['groups'])
                # Aggiorna anche il combo box dei task e il writing group combo
                self.task_group_combo.clear()
                self.task_group_combo.addItems(data['groups'])
                self.task_group_filter.clear()
                self.task_group_filter.addItem("Tutti i gruppi")
                self.task_group_filter.addItems(data['groups'])
                self.writing_group_combo.clear()
                self.writing_group_combo.addItems(data['groups'])
                self.writing_group_combo.setCurrentText('ALL')
                self.chat_area.append('<i style="color: green">Connesso al server</i>')
                
            elif data['type'] == 'system':
                self.chat_area.append(f'<i style="color: gray">{data["message"]}</i>')
                
                # Se il messaggio indica che l'utente è entrato in un nuovo gruppo, aggiorna le flag dei task
                if "entrato nel gruppo" in data["message"] and self.client.username in data["message"]:
                    self.update_task_permissions()
            
            elif data['type'] == 'group_deleted':
                # Ottieni il nome del gruppo eliminato
                deleted_group = data['group_name']
                
                # Rimuovi il gruppo da tutti i combobox
                for combo in [self.group_combo, self.task_group_combo, self.task_group_filter, self.writing_group_combo]:
                    index = combo.findText(deleted_group)
                    if index >= 0:
                        combo.removeItem(index)
                
                # Se il gruppo corrente è stato eliminato, passa al gruppo ALL
                if self.current_group == deleted_group:
                    self.current_group = 'ALL'
                    self.group_combo.setCurrentText('ALL')
                
                # Se il gruppo di scrittura è stato eliminato, passa al gruppo ALL
                if self.writing_group_combo.currentText() == deleted_group:
                    self.writing_group_combo.setCurrentText('ALL')
                
                # Rimuovi i task del gruppo eliminato dalla lista
                i = 0
                while i < self.task_list.topLevelItemCount():
                    item = self.task_list.topLevelItem(i)
                    if item.text(2) == deleted_group:  # La colonna 2 contiene il nome del gruppo
                        self.task_list.takeTopLevelItem(i)
                    else:
                        i += 1
                
                # Mostra un messaggio nell'area chat
                self.chat_area.append(f'<i style="color: orange">{data["message"]}</i>')
            
            elif data['type'] == 'message':
                sender = data.get('from', 'Unknown')
                message = data.get('message', '')
                group = data.get('group', 'ALL')
                sender_group = None
                
                # Cerca il gruppo del mittente dalla lista utenti
                for i in range(self.users_list.count()):
                    item = self.users_list.item(i)
                    user_text = item.text()
                    if user_text.startswith(sender):
                        # Estrai il gruppo tra parentesi quadre se presente
                        if '[' in user_text:
                            sender_group = user_text.split('[')[1].rstrip(']')
                        break
                
                # Verifica se il messaggio deve essere mostrato
                should_show = False
                if group == 'ALL':  # Messaggi in ALL sono visibili a tutti
                    should_show = True
                elif group == self.current_group:  # Messaggi nel gruppo destinatario
                    should_show = True
                elif sender == self.client.username:  # I propri messaggi sono sempre visibili
                    should_show = True
                elif sender_group and sender_group == self.current_group:  # Messaggi da membri del proprio gruppo
                    should_show = True
                
                if should_show:
                    group_info = f" → {group}" if group != 'ALL' else ""
                    
                    # Controlla se il messaggio contiene newline
                    if '\n' in message:
                        # Se ha più righe, metti il nome su una riga separata
                        formatted_message = f'<b>{sender}{group_info}</b>:<br>{message.replace("\n", "<br>")}'
                    else:
                        # Se è una singola riga, mantieni il formato originale
                        formatted_message = f'<b>{sender}{group_info}</b>: {message}'
                    
                    # Aggiungi un colore diverso per i messaggi da altri gruppi
                    if group != self.current_group:
                        formatted_message = f'<span style="color: #666666">{formatted_message}</span>'
                    
                    self.chat_area.append(formatted_message)
            
            elif data['type'] == 'private':
                sender = data.get('from', '')
                to = data.get('to', '')
                if sender:
                    self.chat_area.append(f'<i style="color: purple"><b>PM da {sender}</b>: {data["message"]}</i>')
                else:
                    self.chat_area.append(f'<i style="color: purple"><b>PM a {to}</b>: {data["message"]}</i>')
            
            elif data['type'] == 'error':
                self.chat_area.append(f'<span style="color: red"><i>{data["message"]}</i></span>')
            
            elif data['type'] == 'user_list':
                self.update_users_list(data.get('users', []))
            
            elif data['type'] == 'task_deleted':
                self.chat_area.append(f'<i style="color: green">Task eliminato con successo</i>')
            
            elif data['type'] == 'historical_messages':
                # Gestione dei messaggi storici
                print(f"DEBUG GUI - Elaborazione messaggi storici")
                messages_by_group = data.get('messages', {})
                print(f"DEBUG GUI - Messaggi storici per {len(messages_by_group)} gruppi")
                
                if messages_by_group:
                    self.chat_area.append('<div style="text-align: center; margin: 10px 0; color: #666; font-style: italic;">--- Inizio messaggi storici ---</div>')
                    
                    # Itera attraverso i gruppi
                    for group, messages in messages_by_group.items():
                        print(f"DEBUG GUI - Gruppo {group}: {len(messages)} messaggi")
                        if messages:
                            self.chat_area.append(f'<div style="text-align: center; margin: 5px 0; color: #888; font-weight: bold;">Gruppo: {group}</div>')
                            
                            # Visualizza i messaggi del gruppo
                            for msg in messages:
                                sender = msg.get('sender', 'Unknown')
                                text = msg.get('text', '')
                                timestamp = msg.get('timestamp', '')
                                
                                # Formatta la data in modo leggibile
                                if timestamp:
                                    try:
                                        # Converti da stringa ISO a datetime se necessario
                                        if isinstance(timestamp, str):
                                            from datetime import datetime
                                            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                        
                                        date_str = timestamp.strftime('%d/%m/%Y %H:%M')
                                    except Exception as e:
                                        print(f"DEBUG GUI - Errore formattazione timestamp: {e}")
                                        date_str = ""
                                else:
                                    date_str = ""
                                
                                # Applica uno stile più chiaro per i messaggi storici
                                message_html = f'<span style="color: #888; font-size: 0.95em;"><b>{sender} [{date_str}]</b>: {text}</span>'
                                print(f"DEBUG GUI - Aggiunta messaggio storico: {sender} - {text[:20]}...")
                                self.chat_area.append(message_html)
                    
                    self.chat_area.append('<div style="text-align: center; margin: 10px 0; color: #666; font-style: italic;">--- Fine messaggi storici ---</div>')
                    self.chat_area.append('<div style="text-align: center; margin: 15px 0; color: #333; font-weight: bold;">--- Nuovi messaggi ---</div>')
                    print(f"DEBUG GUI - Completata visualizzazione messaggi storici")
            
            self.chat_area.verticalScrollBar().setValue(
                self.chat_area.verticalScrollBar().maximum()
            )
            QApplication.processEvents()
            
            self.update_window_title()
            
        except Exception as e:
            print(f"Errore gestione messaggio: {e}")

    def send_message(self):
        message = self.message_input.toPlainText().strip()
        if message and self.client.socket:
            if message.startswith('@'):
                # Gestione messaggi privati (codice esistente)
                parts = message[1:].split(' ', 1)
                if len(parts) == 2:
                    target, msg = parts
                    target = target.split('[')[0].strip()
                    users_in_list = [self.users_list.item(i).text().split('[')[0].strip() 
                                   for i in range(self.users_list.count())]
                    
                    if target in users_in_list:
                        data = {
                            'type': 'private_message',
                            'to': target,
                            'message': msg
                        }
                    else:
                        data = {
                            'type': 'group_message',
                            'group': target.upper(),
                            'message': msg
                        }
                else:
                    return
            else:
                # Usa il gruppo selezionato nel writing_group_combo
                target_group = self.writing_group_combo.currentText()
                data = {
                    'type': 'group_message',
                    'group': target_group,
                    'message': message
                }
            
            print(f"DEBUG: Invio messaggio: {data}")
            self.client.send_message(data)
            self.message_input.clear()
            
            # Reset del contatore se siamo nella tab chat
            if self.tab_widget.currentIndex() == self.chat_tab_index:
                self.unread_messages = 0
                self.update_chat_tab()
                self.update_window_title()

    def handle_disconnection(self):
        # Resetta l'interfaccia
        self.login_btn.setText('Login')
        self.login_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
                min-width: 80px;
                background-color: #2ecc71;
                border: none;
                color: white;
            }
            QPushButton:hover {
                opacity: 0.8;
            }
            QPushButton:pressed {
                opacity: 1;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.login_btn.setEnabled(True)
        self.signup_btn.setEnabled(True)
        self.group_combo.setEnabled(False)
        self.group_combo.clear()
        self.group_combo.addItem('ALL')
        self.current_group = 'ALL'
        self.chat_area.append('<i>Connessione persa</i>')
        self.client.socket = None
        self.writing_group_combo.clear()
        self.writing_group_combo.addItem('ALL')
        self.writing_group_combo.setCurrentText('ALL')

    def change_group(self, group):
        if group and group != self.current_group:
            print(f"DEBUG: Cambio gruppo da {self.current_group} a {group}")  # Debug
            self.client.send_message({
                'type': 'join_group',
                'group': group
            })
            self.current_group = group
            # Aggiorna automaticamente il gruppo di destinazione dei messaggi
            self.writing_group_combo.setCurrentText(group)
            
            # Aggiorna i permessi dei task per il nuovo gruppo
            self.update_task_permissions()

    def show_user_context_menu(self, pos):
        """Mostra il menu contestuale per gli utenti"""
        item = self.users_list.itemAt(pos)
        if item and item.text() != self.client.username:
            menu = QMenu()
            send_private = menu.addAction("Invia messaggio privato")
            action = menu.exec_(self.users_list.mapToGlobal(pos))
            
            if action == send_private:
                username = item.text().split('[')[0].strip()  # Rimuove il gruppo se presente
                self.message_input.setFocus()
                self.message_input.setText(f"@{username} ")
                # Sposta il cursore alla fine del testo
                cursor = self.message_input.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.message_input.setTextCursor(cursor)

    def start_private_chat(self, item):
        if isinstance(item, str):
            username = item
        else:
            # Se riceviamo un QListWidgetItem, estraiamo lo username
            username = item.text().split('[')[0].strip()
        
        if username != self.client.username:
            current_text = self.message_input.toPlainText()
            self.message_input.setPlainText(f"@{username} {current_text}")
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
        """Gestisce la chiusura della finestra"""
        if self.client.socket:
            # Invia messaggio di disconnessione al server
            try:
                self.client.send_message({
                    'type': 'disconnect',
                    'username': self.client.username
                })
            except:
                pass
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
                'text': task_text,
                'requester_group': self.current_group  # Aggiungi il gruppo richiedente
            }
            self.client.send_message(data)
            self.task_input.clear()

    def handle_task_status_change(self, item, column):
        if column == 0:  # Prima colonna (Stato)
            task_data = item.data(0, Qt.UserRole)
            if task_data and task_data['group'] == self.current_group:
                is_checked = item.checkState(0) == Qt.Checked
                data = {
                    'type': 'update_task',
                    'task_id': task_data['id'],
                    'completed': is_checked
                }
                print(f"DEBUG: Invio aggiornamento task: {data}")
                self.client.send_message(data)
            else:
                # Ripristina lo stato precedente se l'utente non ha i permessi
                item.setCheckState(0, Qt.Checked if task_data and task_data['completed'] else Qt.Unchecked)

    def update_task_list(self, tasks):
        print(f"DEBUG: Aggiornamento lista task nella GUI")
        current_filter = self.task_group_filter.currentText()
        
        self.task_list.clear()
        
        for task in tasks:
            item = QTreeWidgetItem()
            
            # Imposta lo stato con checkbox e permessi
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            
            # Abilita il checkbox solo se l'utente è nel gruppo del task
            if task['group'] == self.current_group:
                item.setFlags(item.flags() | Qt.ItemIsEnabled)
            else:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            
            item.setCheckState(0, Qt.Checked if task['completed'] else Qt.Unchecked)
            
            # Testo del task, troncato se troppo lungo
            task_text = task['text'].upper()
            if len(task_text) > 30:
                display_text = task_text[:30] + "..."
            else:
                display_text = task_text
                
            if task['completed']:
                item.setText(1, f"✓ {display_text}")
                item.setForeground(1, QColor('#666666'))
                font = item.font(1)
                font.setStrikeOut(True)
                item.setFont(1, font)
            else:
                item.setText(1, display_text)
                item.setForeground(1, QColor('#000000'))
            
            # Altri campi (ID è stato rimosso dalla visualizzazione)
            item.setText(2, task['group'])
            item.setText(3, task.get('requester_group', 'N/A'))
            item.setText(4, task['created_by'])
            item.setText(5, task['date'])
            
            # Informazioni sul completamento
            if task['completed']:
                item.setText(6, task['completed_by'])
                item.setText(7, task['completed_date'])
            else:
                item.setText(6, "")
                item.setText(7, "")
            
            # Memorizza i dati del task nell'item
            item.setData(0, Qt.UserRole, {
                'id': task['id'],
                'group': task['group'],
                'completed': task['completed']
            })
            
            # Crea un tooltip con tutte le informazioni, incluso l'ID
            tooltip = f"""
            <div style='font-family: Arial; font-size: 15pt;'>
                <b>ID:</b> {task['id']}<br>
                <b>Task:</b> {task['text']}<br>
                <b>Gruppo:</b> {task['group']}<br>
                <b>Gruppo Richiedente:</b> {task.get('requester_group', 'N/A')}<br>
                <b>Creato da:</b> {task['created_by']}<br>
                <b>Data creazione:</b> {task['date']}<br>
            """
            
            if task['completed']:
                tooltip += f"""
                <b>Completato da:</b> {task['completed_by']}<br>
                <b>Data completamento:</b> {task['completed_date']}<br>
                """
                
            tooltip += "</div>"
            
            item.setToolTip(1, tooltip)  # Applica il tooltip alla colonna del task
            
            self.task_list.addTopLevelItem(item)
            
            # Nascondi l'item se non corrisponde al filtro corrente
            if current_filter != "Tutti i gruppi" and task['group'] != current_filter:
                item.setHidden(True)
        
        # Adatta le colonne al contenuto
        for i in range(8):  # Una colonna in meno (rimosso ID)
            self.task_list.resizeColumnToContents(i)
        
        # Forza la larghezza minima della colonna Task
        self.task_list.setColumnWidth(1, max(self.config['client']['chat']['min_task_width'], self.task_list.columnWidth(1)))

    def filter_tasks(self):
        selected_group = self.task_group_filter.currentText()
        
        # Abilita/disabilita pulsante PDF
        can_export = selected_group != "Tutti i gruppi" and selected_group == self.current_group
        self.pdf_btn.setEnabled(can_export)
        
        for i in range(self.task_list.topLevelItemCount()):
            item = self.task_list.topLevelItem(i)
            if selected_group == "Tutti i gruppi" or item.text(2) == selected_group:
                item.setHidden(False)
            else:
                item.setHidden(True)

    def export_to_pdf(self):
        selected_group = self.task_group_filter.currentText()
        if selected_group != self.current_group:
            return
        
        try:
            # Crea lista dei task incompleti del gruppo
            tasks_to_export = []
            for i in range(self.task_list.topLevelItemCount()):
                item = self.task_list.topLevelItem(i)
                if item.text(2) == selected_group and item.checkState(0) == Qt.Unchecked:
                    tasks_to_export.append({
                        'task': item.text(1),
                        'date': item.text(5)
                    })

            if not tasks_to_export:
                self.chat_area.append('<i style="color: blue">Non ci sono task da completare per questo gruppo</i>')
                return

            # Crea il PDF
            filename = f"tasks_pending_{selected_group}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            doc = SimpleDocTemplate(
                filename, 
                pagesize=A4,
                leftMargin=36, 
                rightMargin=36, 
                topMargin=36, 
                bottomMargin=36
            )
            elements = []

            # Stili
            styles = getSampleStyleSheet()
            
            # Crea stili personalizzati
            header_style = ParagraphStyle(
                'Header',
                parent=styles['Heading1'],
                fontSize=16,
                alignment=1,  # Centrato
                spaceAfter=10,
                textColor=colors.darkblue
            )
            
            title_style = ParagraphStyle(
                'Title',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=20,
                textColor=colors.darkblue
            )
            
            subtitle_style = ParagraphStyle(
                'Subtitle',
                parent=styles['Heading3'],
                fontSize=12,
                spaceAfter=5,
                textColor=colors.darkblue
            )
            
            normal_style = ParagraphStyle(
                'Normal',
                parent=styles['Normal'],
                fontSize=10,
                spaceBefore=5,
                spaceAfter=5
            )
            
            info_style = ParagraphStyle(
                'Info',
                parent=styles['Italic'],
                fontSize=8,
                textColor=colors.grey
            )
            
            # Nome programma dall'intestazione
            program_name = self.config['client']['window']['title']
            
            # Intestazione
            elements.append(Paragraph(program_name, header_style))
            elements.append(Paragraph(f"Elenco Task da Completare", title_style))
            elements.append(Paragraph(f"Gruppo: {selected_group}", subtitle_style))
            
            # Separatore
            elements.append(Spacer(1, 10))
            elements.append(Paragraph(f"<hr width='100%'/>", normal_style))
            elements.append(Spacer(1, 20))
            
            # Dati per la tabella
            data = [['Descrizione Task', 'Data creazione']]
            
            # Larghezze colonne (in % della pagina)
            col_widths = [doc.width * 0.75, doc.width * 0.25]
            
            # Aggiungi i task alla tabella
            for task in tasks_to_export:
                # Gestisci il testo lungo permettendo il wrapping nelle celle
                task_text = Paragraph(task['task'], normal_style)
                date_text = Paragraph(task['date'], normal_style)
                data.append([task_text, date_text])

            # Crea tabella con larghezze colonne specificate
            table = Table(data, colWidths=col_widths)
            
            # Stile tabella
            table.setStyle(TableStyle([
                # Intestazione
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGNMENT', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                
                # Corpo tabella - alternanza colori righe
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                
                # Allineamento
                ('ALIGNMENT', (0, 1), (0, -1), 'LEFT'),  # Task allineati a sinistra
                ('ALIGNMENT', (1, 1), (1, -1), 'CENTER'),  # Date centrate
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                
                # Padding celle
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('LEFTPADDING', (0, 1), (0, -1), 10),
                
                # Bordi e separatori
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.darkblue),  # Linea più spessa sotto l'intestazione
            ]))
            
            elements.append(table)

            # Aggiungi informazioni finali
            elements.append(Spacer(1, 20))
            current_date = datetime.now().strftime('%d/%m/%Y alle %H:%M')
            elements.append(Paragraph(
                f"Report generato il {current_date}", 
                info_style
            ))
            
            # Numero totale di task
            elements.append(Spacer(1, 5))
            elements.append(Paragraph(
                f"Totale task da completare: {len(tasks_to_export)}", 
                info_style
            ))

            # Piè di pagina
            def add_page_number(canvas, doc):
                canvas.saveState()
                canvas.setFont('Helvetica', 8)
                canvas.setFillColor(colors.grey)
                page_num = f"Pagina {doc.page}"
                canvas.drawRightString(doc.pagesize[0] - 36, 36, page_num)
                canvas.restoreState()

            # Genera il PDF con numeri di pagina
            doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)

            # Apri il PDF con l'applicazione predefinita
            if platform.system() == 'Darwin':       # macOS
                subprocess.run(['open', filename])
            elif platform.system() == 'Windows':    # Windows
                os.startfile(filename)
            else:                                   # Linux
                subprocess.run(['xdg-open', filename])

            self.chat_area.append(f'<i style="color: green">PDF dei task pendenti esportato come {filename}</i>')

        except Exception as e:
            self.chat_area.append(f'<i style="color: red">Errore durante l\'esportazione del PDF: {str(e)}</i>')

    def handle_tab_change(self, index):
        # Se torniamo alla tab Chat, resetta il contatore
        if index == self.chat_tab_index:
            self.unread_messages = 0
            self.update_chat_tab()
            self.update_window_title()
            # Resetta il colore della tab
            self.tab_widget.tabBar().setTabTextColor(
                self.chat_tab_index, 
                QColor('black')
            )

    def update_chat_tab(self):
        if self.unread_messages > 0:
            self.tab_widget.setTabText(self.chat_tab_index, f"Chat ({self.unread_messages})")
            self.tab_widget.tabBar().setTabTextColor(
                self.chat_tab_index, 
                QColor('#0078d7')
            )
        else:
            self.tab_widget.setTabText(self.chat_tab_index, "Chat")
            self.tab_widget.tabBar().setTabTextColor(
                self.chat_tab_index, 
                QColor('black')
            )

    def update_window_title(self):
        base_title = "Chat Client"
        if self.unread_messages > 0:
            self.setWindowTitle(f"{base_title} ({self.unread_messages})")
        else:
            self.setWindowTitle(base_title)

    def flash_tab(self):
        if self.flash_count < 6:  # Flash per 3 volte (on-off)
            self.is_flashing = not self.is_flashing
            if self.is_flashing:
                self.tab_widget.tabBar().setTabTextColor(
                    self.chat_tab_index, 
                    QColor('#0078d7')
                )
            else:
                self.tab_widget.tabBar().setTabTextColor(
                    self.chat_tab_index, 
                    QColor('black')
                )
            self.flash_count += 1
        else:
            self.flash_timer.stop()
            self.flash_count = 0
            if self.unread_messages > 0:
                self.tab_widget.tabBar().setTabTextColor(
                    self.chat_tab_index, 
                    QColor('#0078d7')
                )

    def handle_message_input_keypress(self, event):
        # Invia con Enter, va a capo con Shift+Enter
        if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
            self.send_message()
            event.accept()  # Previene il comportamento predefinito
        else:
            # Se è Shift+Enter o qualsiasi altro tasto, comportamento normale
            QTextEdit.keyPressEvent(self.message_input, event)

    def handle_task_input_keypress(self, event):
        # Invia con Enter
        if event.key() == Qt.Key_Return:
            self.create_task()
            event.accept()  # Previene il comportamento predefinito
        else:
            # Per qualsiasi altro tasto, comportamento normale
            QLineEdit.keyPressEvent(self.task_input, event)

    def change_writing_group(self, group):
        """Cambia solo il gruppo di destinazione del messaggio"""
        if group:
            # Non aggiorniamo più la label poiché l'abbiamo rimossa
            pass

    def show_task_context_menu(self, position):
        menu = QMenu()
        item = self.task_list.itemAt(position)
        
        if item:
            task_data = item.data(0, Qt.UserRole)
            if task_data:
                # Verifica se l'utente corrente è il creatore del task
                creator = item.text(4)  # Colonna "Creato da" (indice aggiornato)
                if creator == self.client.username:
                    delete_action = menu.addAction("Elimina task")
                    action = menu.exec_(self.task_list.mapToGlobal(position))
                    
                    if action == delete_action:
                        self.delete_task(task_data['id'])

    def delete_task(self, task_id):
        data = {
            'type': 'delete_task',
            'task_id': task_id
        }
        print(f"DEBUG: Invio richiesta eliminazione task: {data}")
        self.client.send_message(data)

    def update_task_permissions(self):
        """Aggiorna i permessi dei task in base al gruppo corrente dell'utente"""
        for i in range(self.task_list.topLevelItemCount()):
            item = self.task_list.topLevelItem(i)
            task_data = item.data(0, Qt.UserRole)
            
            # Abilita o disabilita l'interazione con i task
            if task_data and task_data['group'] == self.current_group:
                item.setFlags(item.flags() | Qt.ItemIsEnabled)
            else:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            
            # Aggiorna lo stile visivo per riflettere lo stato di abilitazione
            if task_data['group'] == self.current_group:
                item.setForeground(1, QColor('#000000') if not task_data['completed'] else QColor('#666666'))
            else:
                item.setForeground(1, QColor('#777777'))

def main():
    app = QApplication([])
    window = ChatWindow()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main() 