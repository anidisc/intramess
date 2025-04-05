# IntraMess Mobile

Versione mobile web di IntraMess, un'applicazione di messaggistica istantanea per gruppi.

## Requisiti

- Python 3.8+
- Flask
- Socket.IO
- Browser moderno con supporto JavaScript ES6+

## Installazione

1. Clona il repository
2. Installa le dipendenze:

```bash
pip install flask flask-socketio
```

1. Assicurati che il file di configurazione `config.json` sia presente nella directory principale del progetto

## Avvio

Per avviare l'applicazione mobile:

```bash
python app.py
```

L'applicazione sarà accessibile all'indirizzo `http://localhost:5001`

## Funzionalità

- **Autenticazione**
  - Registrazione nuovi utenti
  - Login con username e password
  - Logout
- **Messaggistica**
  - Chat di gruppo
  - Messaggi privati (usando @username)
  - Selezione del gruppo corrente
  - Visualizzazione messaggi in tempo reale
- **Gestione Task**
  - Creazione nuovi task
  - Visualizzazione stato task
  - Filtraggio per gruppo
- **Gestione Utenti**
  - Lista utenti online
  - Visualizzazione gruppo di appartenenza
  - Avvio rapido messaggi privati

## Interfaccia Mobile

L'applicazione è ottimizzata per dispositivi mobili con:

- Design responsive
- Interfaccia touch-friendly
- Gestione modale per azioni complesse
- Notifiche toast per feedback
- Scrolling fluido

## Note Tecniche

- L'applicazione utilizza polling per l'aggiornamento dei messaggi
- La connessione al server principale avviene tramite socket
- I dati vengono sincronizzati automaticamente ogni secondo
- L'interfaccia si adatta automaticamente alle dimensioni dello schermo

## Sicurezza

- Le password vengono hashate prima dell'invio
- Le sessioni sono gestite lato server
- I messaggi privati sono visibili solo ai destinatari
- La connessione è protetta tramite HTTPS (se configurato)

## Supporto

Per segnalare bug o richiedere nuove funzionalità, apri una issue su GitHub.