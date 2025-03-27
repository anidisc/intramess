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
        self.unread_messages = 0
        self.init_ui()
        self.setup_signals()
        self.flash_timer = QTimer()
        self.flash_timer.timeout.connect(self.flash_tab)
        self.is_flashing = False
        self.flash_count = 0

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
        
        # Area chat con più spazio
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        chat_layout.addWidget(self.chat_area, stretch=7)  # Diamo più spazio alla chat

        # Area input messaggio
        msg_layout = QVBoxLayout()
        
        # Input box più compatto
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Scrivi il tuo messaggio...")
        self.message_input.setFixedHeight(60)  # Altezza fissa per 3 linee circa
        
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
            "ID", 
            "Task", 
            "Gruppo", 
            "Gruppo Richiedente",  # Nuovo campo
            "Creato da", 
            "Data", 
            "Completato da", 
            "Data completamento"
        ])
        self.task_list.setAlternatingRowColors(True)
        
        # Imposta la larghezza minima della colonna Task
        self.task_list.setColumnWidth(2, 300)  # Colonna Task più larga
        
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
        self.connect_btn.setStyleSheet(connect_button_style)
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
        
        self.username_input.setStyleSheet(input_style)
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
        self.connect_btn.clicked.connect(self.handle_connection)
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

    def handle_connection(self):
        if self.client.socket:
            # Invia messaggio di disconnessione al server
            try:
                self.client.send_message({
                    'type': 'disconnect',
                    'username': self.client.username
                })
            except:
                pass  # Se la connessione è già interrotta, ignora l'errore
            
            # Disconnetti il client
            self.client.disconnect()
            
            # Resetta l'interfaccia
            self.connect_btn.setProperty('connected', False)
            self.connect_btn.style().unpolish(self.connect_btn)
            self.connect_btn.style().polish(self.connect_btn)
            self.connect_btn.setText('Connetti')
            self.username_input.setEnabled(True)
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
            username = self.username_input.text().strip()
            if username:
                if self.client.connect_to_server('localhost', 5000, username):
                    self.connect_btn.setProperty('connected', True)
                    self.connect_btn.style().unpolish(self.connect_btn)
                    self.connect_btn.style().polish(self.connect_btn)
                    self.connect_btn.setText('Disconnetti')
                    self.username_input.setEnabled(False)
                else:
                    self.chat_area.append('<span style="color: red">Errore di connessione</span>')

    def handle_message(self, data):
        try:
            print(f"DEBUG GUI - Gestione messaggio: {data}")
            
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
            
            elif data['type'] == 'system':
                self.chat_area.append(f'<i style="color: gray">{data["message"]}</i>')
            
            elif data['type'] == 'error':
                self.chat_area.append(f'<span style="color: red"><i>{data["message"]}</i></span>')
            
            elif data['type'] == 'user_list':
                self.update_users_list(data.get('users', []))
            
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
        self.connect_btn.setProperty('connected', False)
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)
        self.connect_btn.setText('Connetti')
        self.username_input.setEnabled(True)
        self.group_combo.setEnabled(False)  # Disabilita il combo box alla disconnessione
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
            if task['group'] == self.current_group:
                item.setFlags(item.flags() | Qt.ItemIsEnabled)
            else:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            
            item.setCheckState(0, Qt.Checked if task['completed'] else Qt.Unchecked)
            
            # ID (seconda colonna)
            item.setText(1, str(task['id']))
            
            # Testo del task in maiuscolo
            if task['completed']:
                item.setText(2, f"✓ {task['text'].upper()}")
                item.setForeground(2, QColor('#666666'))
                font = item.font(2)
                font.setStrikeOut(True)
                item.setFont(2, font)
            else:
                item.setText(2, task['text'].upper())
                item.setForeground(2, QColor('#000000'))
            
            # Altri campi
            item.setText(3, task['group'])
            item.setText(4, task.get('requester_group', 'N/A'))  # Nuovo campo
            item.setText(5, task['created_by'])
            item.setText(6, task['date'])
            
            # Informazioni sul completamento
            if task['completed']:
                item.setText(7, task['completed_by'])
                item.setText(8, task['completed_date'])
            else:
                item.setText(7, "")
                item.setText(8, "")
            
            # Memorizza i dati del task nell'item
            item.setData(0, Qt.UserRole, {
                'id': task['id'],
                'group': task['group'],
                'completed': task['completed']
            })
            
            self.task_list.addTopLevelItem(item)
            
            # Nascondi l'item se non corrisponde al filtro corrente
            if current_filter != "Tutti i gruppi" and task['group'] != current_filter:
                item.setHidden(True)
        
        # Adatta le colonne al contenuto
        for i in range(9):  # Aggiornato il numero di colonne
            self.task_list.resizeColumnToContents(i)
        
        # Forza la larghezza minima della colonna Task
        self.task_list.setColumnWidth(2, max(300, self.task_list.columnWidth(2)))

    def filter_tasks(self):
        selected_group = self.task_group_filter.currentText()
        
        # Abilita/disabilita pulsante PDF
        can_export = selected_group != "Tutti i gruppi" and selected_group == self.current_group
        self.pdf_btn.setEnabled(can_export)
        
        for i in range(self.task_list.topLevelItemCount()):
            item = self.task_list.topLevelItem(i)
            if selected_group == "Tutti i gruppi" or item.text(3) == selected_group:
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
                if item.text(3) == selected_group and item.checkState(0) == Qt.Unchecked:
                    tasks_to_export.append({
                        'id': item.text(1),
                        'task': item.text(2),
                        'created_by': item.text(4),
                        'date': item.text(5)
                    })

            if not tasks_to_export:
                self.chat_area.append('<i style="color: blue">Non ci sono task da completare per questo gruppo</i>')
                return

            # Crea il PDF
            filename = f"tasks_pending_{selected_group}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            doc = SimpleDocTemplate(filename, pagesize=A4)
            elements = []

            # Stili
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30
            )

            # Titolo
            elements.append(Paragraph(f"Task da completare - Gruppo {selected_group}", title_style))
            elements.append(Spacer(1, 20))

            # Dati per la tabella
            data = [['ID', 'Task', 'Creato da', 'Data creazione']]
            for task in tasks_to_export:
                data.append([
                    task['id'],
                    task['task'],
                    task['created_by'],
                    task['date']
                ])

            # Crea tabella
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(table)

            # Aggiungi data e ora di generazione
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(
                f"Report generato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}",
                styles['Italic']
            ))

            # Genera il PDF
            doc.build(elements)

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

def main():
    app = QApplication([])
    window = ChatWindow()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main() 