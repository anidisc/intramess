// Gestione dello stato dell'applicazione
let currentUser = null;
let currentGroup = 'ALL';
let messagePollingInterval = null;

// Inizializzazione dell'applicazione
document.addEventListener('DOMContentLoaded', () => {
    // Mostra il modal di autenticazione
    const authModal = new bootstrap.Modal(document.getElementById('authModal'));
    authModal.show();

    // Gestione form di login
    document.getElementById('loginForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const credentials = {
            username: formData.get('username'),
            password: formData.get('password')
        };

        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(credentials)
            });

            const data = await response.json();
            if (data.success) {
                currentUser = credentials.username;
                document.getElementById('currentUser').textContent = currentUser;
                document.getElementById('authModal').classList.remove('show');
                document.getElementById('appContainer').classList.remove('d-none');
                startMessagePolling();
                showToast('Login effettuato con successo', 'success');
            } else {
                showToast(data.message, 'error');
            }
        } catch (error) {
            showToast('Errore durante il login', 'error');
        }
    });

    // Gestione form di registrazione
    document.getElementById('registerForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        if (formData.get('password') !== formData.get('confirmPassword')) {
            showToast('Le password non coincidono', 'error');
            return;
        }

        const credentials = {
            username: formData.get('username'),
            password: formData.get('password')
        };

        try {
            const response = await fetch('/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(credentials)
            });

            const data = await response.json();
            if (data.success) {
                showToast('Registrazione effettuata con successo', 'success');
                // Passa alla tab di login
                document.querySelector('#authTabs a[href="#loginTab"]').click();
                e.target.reset();
            } else {
                showToast(data.message, 'error');
            }
        } catch (error) {
            showToast('Errore durante la registrazione', 'error');
        }
    });

    // Gestione invio messaggi
    document.getElementById('sendMessage').addEventListener('click', sendMessage);
    document.getElementById('messageInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Gestione cambio gruppo
    document.getElementById('groupSelect').addEventListener('change', (e) => {
        currentGroup = e.target.value;
        updateMessages();
    });

    // Gestione creazione task
    document.getElementById('createTaskBtn').addEventListener('click', () => {
        const modal = new bootstrap.Modal(document.getElementById('createTaskModal'));
        modal.show();
    });

    document.getElementById('createTaskForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const taskData = {
            type: 'create_task',
            group: formData.get('group'),
            text: formData.get('text')
        };

        try {
            const response = await fetch('/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(taskData)
            });

            const data = await response.json();
            if (data.success) {
                showToast('Task creato con successo', 'success');
                bootstrap.Modal.getInstance(document.getElementById('createTaskModal')).hide();
                e.target.reset();
            } else {
                showToast('Errore durante la creazione del task', 'error');
            }
        } catch (error) {
            showToast('Errore durante la creazione del task', 'error');
        }
    });

    // Gestione logout
    document.getElementById('logoutBtn').addEventListener('click', async () => {
        try {
            const response = await fetch('/logout');
            const data = await response.json();
            if (data.success) {
                stopMessagePolling();
                currentUser = null;
                document.getElementById('appContainer').classList.add('d-none');
                document.getElementById('authModal').classList.add('show');
                showToast('Logout effettuato con successo', 'success');
            }
        } catch (error) {
            showToast('Errore durante il logout', 'error');
        }
    });

    // Gestione cambio tab
    document.querySelectorAll('.nav-link[data-tab]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = e.target.getAttribute('data-tab');
            switchTab(tabId);
        });
    });
});

// Funzioni di utilità
function startMessagePolling() {
    if (messagePollingInterval) return;
    messagePollingInterval = setInterval(pollMessages, 1000);
}

function stopMessagePolling() {
    if (messagePollingInterval) {
        clearInterval(messagePollingInterval);
        messagePollingInterval = null;
    }
}

async function pollMessages() {
    try {
        const [messagesResponse, usersResponse, tasksResponse] = await Promise.all([
            fetch('/messages'),
            fetch('/users'),
            fetch('/tasks')
        ]);

        const messages = await messagesResponse.json();
        const users = await usersResponse.json();
        const tasks = await tasksResponse.json();

        updateMessages(messages);
        updateUsersList(users);
        updateTasksList(tasks);
    } catch (error) {
        console.error('Errore durante il polling:', error);
    }
}

function updateMessages(messages) {
    const messagesContainer = document.getElementById('messages');
    messagesContainer.innerHTML = '';

    messages.forEach(msg => {
        if (msg.group === currentGroup || currentGroup === 'ALL') {
            const messageElement = document.createElement('div');
            messageElement.className = `message ${msg.from === currentUser ? 'sent' : 'received'}`;
            
            let messageContent = '';
            if (msg.type === 'private') {
                messageElement.classList.add('private');
                messageContent = `PM ${msg.from === currentUser ? 'a' : 'da'} ${msg.from === currentUser ? msg.to : msg.from}: ${msg.message}`;
            } else {
                messageContent = `${msg.from}: ${msg.message}`;
            }
            
            messageElement.textContent = messageContent;
            messagesContainer.appendChild(messageElement);
        }
    });

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function updateUsersList(users) {
    const usersList = document.getElementById('usersList');
    usersList.innerHTML = '';

    Object.entries(users).forEach(([username, info]) => {
        const userElement = document.createElement('a');
        userElement.className = 'list-group-item list-group-item-action';
        userElement.innerHTML = `
            <i class="fas fa-user"></i>
            ${username} ${info.group !== 'ALL' ? `<span class="badge bg-secondary">${info.group}</span>` : ''}
        `;
        userElement.addEventListener('click', () => {
            document.getElementById('messageInput').value = `@${username} `;
            document.getElementById('messageInput').focus();
        });
        usersList.appendChild(userElement);
    });
}

function updateTasksList(tasks) {
    const tasksList = document.getElementById('tasksList');
    tasksList.innerHTML = '';

    tasks.forEach(task => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <div class="task-status ${task.completed ? 'completed' : 'pending'}"></div>
            </td>
            <td>${task.text}</td>
            <td>${task.group}</td>
            <td>${task.created_by}</td>
            <td>${task.date}</td>
        `;
        tasksList.appendChild(row);
    });
}

async function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    
    if (!message) return;

    let messageData;
    if (message.startsWith('@')) {
        const parts = message.slice(1).split(' ', 1);
        if (parts.length === 2) {
            const [target, text] = parts;
            messageData = {
                type: 'private_message',
                to: target,
                message: text
            };
        }
    } else {
        messageData = {
            type: 'group_message',
            group: currentGroup,
            message: message
        };
    }

    if (messageData) {
        try {
            const response = await fetch('/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(messageData)
            });

            const data = await response.json();
            if (data.success) {
                messageInput.value = '';
            } else {
                showToast('Errore durante l\'invio del messaggio', 'error');
            }
        } catch (error) {
            showToast('Errore durante l\'invio del messaggio', 'error');
        }
    }
}

function switchTab(tabId) {
    // Aggiorna le tab attive
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });

    // Attiva la tab selezionata
    document.getElementById(`${tabId}Tab`).classList.add('active');
    document.querySelector(`.nav-link[data-tab="${tabId}"]`).classList.add('active');
}

function showToast(message, type = 'info') {
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="toast-header">
            <strong class="me-auto">${type === 'success' ? 'Successo' : 'Errore'}</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    toastContainer.appendChild(toast);
    document.body.appendChild(toastContainer);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', () => {
        toastContainer.remove();
    });
} 