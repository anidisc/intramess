from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette, QColor

class SignupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Registrazione')
        self.setFixedSize(650, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #2c3e50;
                border-radius: 10px;
            }
            QLabel {
                color: #ecf0f1;
                font-size: 16pt;
                font-weight: bold;
                margin-bottom: 15px;
            }
            QLineEdit {
                padding: 15px;
                border: 2px solid #3498db;
                border-radius: 5px;
                background-color: #34495e;
                color: #ecf0f1;
                font-size: 14pt;
                min-width: 300px;
                min-height: 25px;
            }
            QLineEdit:focus {
                border: 2px solid #2980b9;
            }
            QPushButton {
                padding: 15px 30px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14pt;
                min-width: 150px;
                min-height: 40px;
                background-color: #3498db;
                border: none;
                color: white;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #2472a4;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(25)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Titolo
        title_label = QLabel('Registrazione')
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                font-size: 32pt;
                font-weight: bold;
                margin-bottom: 30px;
            }
        """)
        layout.addWidget(title_label)
        
        # Username
        username_layout = QHBoxLayout()
        username_layout.setSpacing(20)
        username_label = QLabel('Username:')
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('Inserisci il tuo username')
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_input)
        layout.addLayout(username_layout)
        
        # Password
        password_layout = QHBoxLayout()
        password_layout.setSpacing(20)
        password_label = QLabel('Password:')
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('Inserisci la tua password')
        self.password_input.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        layout.addLayout(password_layout)
        
        # Conferma Password
        confirm_password_layout = QHBoxLayout()
        confirm_password_layout.setSpacing(20)
        confirm_password_label = QLabel('Conferma:')
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText('Conferma la tua password')
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        confirm_password_layout.addWidget(confirm_password_label)
        confirm_password_layout.addWidget(self.confirm_password_input)
        layout.addLayout(confirm_password_layout)
        
        # Pulsante Registrazione
        self.signup_button = QPushButton('Registrati')
        self.signup_button.setCursor(Qt.PointingHandCursor)
        self.signup_button.clicked.connect(self.validate_and_accept)
        layout.addWidget(self.signup_button, alignment=Qt.AlignCenter)
        
        self.setLayout(layout)
        
    def validate_and_accept(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()
        
        if not username:
            QMessageBox.warning(self, 'Errore', 'L\'username non può essere vuoto')
            return
            
        if not password:
            QMessageBox.warning(self, 'Errore', 'La password non può essere vuota')
            return
            
        if password != confirm_password:
            QMessageBox.warning(self, 'Errore', 'Le password non coincidono')
            return
            
        if len(password) < 6:
            QMessageBox.warning(self, 'Errore', 'La password deve essere di almeno 6 caratteri')
            return
            
        self.accept()
        
    def get_credentials(self):
        return {
            'username': self.username_input.text().strip(),
            'password': self.password_input.text()
        } 