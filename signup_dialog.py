from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt

class SignupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrazione")
        self.setFixedWidth(300)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Username
        username_layout = QHBoxLayout()
        username_label = QLabel("Username:")
        self.username_input = QLineEdit()
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_input)
        layout.addLayout(username_layout)
        
        # Password
        password_layout = QHBoxLayout()
        password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        layout.addLayout(password_layout)
        
        # Conferma Password
        confirm_layout = QHBoxLayout()
        confirm_label = QLabel("Conferma:")
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.Password)
        confirm_layout.addWidget(confirm_label)
        confirm_layout.addWidget(self.confirm_input)
        layout.addLayout(confirm_layout)
        
        # Pulsanti
        button_layout = QHBoxLayout()
        self.signup_button = QPushButton("Registrati")
        self.signup_button.clicked.connect(self.validate_and_accept)
        button_layout.addWidget(self.signup_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def validate_and_accept(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        
        if not username:
            QMessageBox.warning(self, "Errore", "Inserisci un username")
            return
            
        if not password:
            QMessageBox.warning(self, "Errore", "Inserisci una password")
            return
            
        if password != confirm:
            QMessageBox.warning(self, "Errore", "Le password non coincidono")
            return
            
        if len(password) < 6:
            QMessageBox.warning(self, "Errore", "La password deve essere di almeno 6 caratteri")
            return
            
        self.accept()
        
    def get_credentials(self):
        return {
            'username': self.username_input.text().strip(),
            'password': self.password_input.text()
        } 