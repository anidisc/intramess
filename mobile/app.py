from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
import json
import socket
import threading
import os
from datetime import timedelta
from database import Database

app = Flask(__name__)

# Configurazione della sessione - uso una chiave fissa per evitare reset delle sessioni
app.config['SECRET_KEY'] = 'intramess-mobile-secret-key'  # Chiave fissa
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(__file__), 'flask_session')
app.config['SESSION_USE_SIGNER'] = True
Session(app)

# Assicurati che la directory per le sessioni esista
if not os.path.exists(app.config['SESSION_FILE_DIR']):
    os.makedirs(app.config['SESSION_FILE_DIR'])

# Configurazione del client
class WebClient:
    def __init__(self, config_file=None):
        self.socket = None
        self.running = False
        self.username = None
        self.config_file = config_file
        self.config = self.load_config()
        self.messages = []
        self.users = {}
        self.tasks = []
        self.receiver_thread = None

    def load_config(self):
        try:
            if self.config_file:
                config_path = self.config_file
            else:
                config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
            
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Errore nel caricamento della configurazione: {e}")
            return {
                "server": {
                    "host": "localhost",
                    "port": 5000
                }
            }

    def connect_to_server(self, credentials):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.config['server']['host'], self.config['server']['port']))
            
            # Invia credenziali di login
            self.socket.send(json.dumps({
                'type': 'login',
                'username': credentials['username'],
                'password': credentials['password']
            }).encode())
            
            # Ricevi risposta
            response = json.loads(self.socket.recv(4096).decode())
            if response.get('type') == 'error':
                self.socket.close()
                self.socket = None
                return False, response.get('message', 'Errore di connessione')
            
            self.username = credentials['username']
            
            # Avvia thread ricezione
            self.running = True
            self.receiver_thread = threading.Thread(target=self.receive_messages)
            self.receiver_thread.daemon = True
            self.receiver_thread.start()
            
            return True, response
        except Exception as e:
            return False, str(e)

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
                            self.handle_message(msg_data)
                        except json.JSONDecodeError:
                            continue
            except:
                break
        
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None

    def handle_message(self, data):
        msg_type = data.get('type')
        
        if msg_type == 'message':
            self.messages.append(data)
        elif msg_type == 'private':
            self.messages.append(data)
        elif msg_type == 'user_list':
            self.users = data.get('users', {})
        elif msg_type == 'task_list':
            self.tasks = data.get('tasks', [])
        elif msg_type == 'historical_messages':
            for group, msgs in data.get('messages', {}).items():
                for msg in msgs:
                    self.messages.append(msg)
        elif msg_type == 'connection_accepted':
            # Memorizza i gruppi disponibili
            if 'groups' in data:
                self.groups = data.get('groups', ['ALL'])

    def send_message(self, message):
        if self.socket and self.running:
            try:
                self.socket.send(json.dumps(message).encode())
                return True
            except:
                return False
        return False

    def disconnect(self):
        self.running = False
        if self.socket:
            try:
                self.socket.send(json.dumps({
                    'type': 'disconnect'
                }).encode())
            except:
                pass
            self.socket.close()
            self.socket = None
        self.messages = []
        self.users = {}
        self.tasks = []

# Dizionario per tenere traccia dei client attivi
clients = {}

@app.before_request
def check_session():
    # Ignora le richieste per risorse statiche e la pagina di login/registrazione
    if request.endpoint in ['static', 'login', 'register'] or request.path == '/':
        return
    
    # Se non c'è una sessione attiva, reindirizza al login per le richieste API
    if 'username' not in session and request.path.startswith('/'):
        if request.content_type == 'application/json':
            return jsonify({'success': False, 'message': 'Sessione scaduta'}), 401
        return redirect(url_for('index'))

@app.route('/')
def index():
    if 'username' in session:
        # L'utente è già loggato, controlla se il client esiste
        if session['username'] in clients and clients[session['username']].running:
            client = clients[session['username']]
            return render_template('index.html', 
                                  logged_in=True, 
                                  username=session['username'],
                                  groups=getattr(client, 'groups', ['ALL']))
    
    # Se l'utente non è loggato o il client non esiste/non è connesso
    return render_template('index.html', logged_in=False)

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    # Crea un nuovo client se non esiste
    if username not in clients:
        clients[username] = WebClient()
    
    # Tenta la connessione
    success, message = clients[username].connect_to_server({
        'username': username,
        'password': password
    })
    
    if success:
        session.permanent = True
        session['username'] = username
        
        # Restituisci anche i gruppi disponibili
        client = clients[username]
        groups = getattr(client, 'groups', ['ALL'])
        
        return jsonify({'success': True, 'groups': groups})
    else:
        if username in clients:
            del clients[username]
        return jsonify({'success': False, 'message': message})

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    try:
        # Crea una connessione al database
        db = Database()
        
        # Tenta la registrazione
        success, message = db.register_user(username, password)
        
        if success:
            # Se la registrazione ha successo, effettua il login
            if username not in clients:
                clients[username] = WebClient()
            
            # Tenta la connessione
            login_success, login_response = clients[username].connect_to_server({
                'username': username,
                'password': password
            })
            
            if login_success:
                session.permanent = True
                session['username'] = username
                
                # Restituisci anche i gruppi disponibili
                client = clients[username]
                groups = getattr(client, 'groups', ['ALL'])
                
                return jsonify({'success': True, 'message': message, 'groups': groups})
            else:
                if username in clients:
                    del clients[username]
                return jsonify({'success': False, 'message': str(login_response)})
        else:
            return jsonify({'success': False, 'message': message})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/logout', methods=['POST'])
def logout():
    username = session.get('username')
    if username and username in clients:
        clients[username].disconnect()
        del clients[username]
    session.clear()
    return jsonify({'success': True})

@app.route('/messages')
def get_messages():
    username = session.get('username')
    if username and username in clients:
        return jsonify(clients[username].messages)
    return jsonify([])

@app.route('/users')
def get_users():
    username = session.get('username')
    if username and username in clients:
        return jsonify(clients[username].users)
    return jsonify({})

@app.route('/tasks')
def get_tasks():
    username = session.get('username')
    if username and username in clients:
        return jsonify(clients[username].tasks)
    return jsonify([])

@app.route('/groups')
def get_groups():
    username = session.get('username')
    if username and username in clients:
        client = clients[username]
        groups = getattr(client, 'groups', ['ALL'])
        return jsonify(groups)
    return jsonify(['ALL'])

@app.route('/send_message', methods=['POST'])
def send_message():
    username = session.get('username')
    if username and username in clients:
        data = request.get_json()
        if clients[username].send_message(data):
            return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/check_session')
def check_session_status():
    if 'username' in session:
        username = session['username']
        if username in clients and clients[username].running:
            return jsonify({'logged_in': True, 'username': username})
    return jsonify({'logged_in': False})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True) 