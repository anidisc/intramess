from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette, QColor

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Login')
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
        title_label = QLabel('Login')
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
        
        # Pulsante Login
        self.login_button = QPushButton('Login')
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.clicked.connect(self.accept)
        layout.addWidget(self.login_button, alignment=Qt.AlignCenter)
        
        self.setLayout(layout)
        
    def get_credentials(self):
        return {
            'username': self.username_input.text(),
            'password': self.password_input.text()
        } 