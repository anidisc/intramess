# Server di Messaggistica

Un server di messaggistica in Python che permette la comunicazione tra più client con supporto per messaggi privati e broadcast.

## Requisiti

- Python 3.6 o superiore
- colorama

## Installazione

1. Clona il repository
2. Installa le dipendenze:
```bash
pip install -r requirements.txt
```

## Utilizzo

### Avvio del Server

Per avviare il server, esegui:
```bash
python server.py
```

Il server si avvierà sulla porta 5000 (localhost) di default.

Comandi disponibili per il server:
- `list`: mostra tutti i client connessi
- `kick <username>`: disconnette un utente specifico
- `log`: mostra gli ultimi 10 log
- `stop`: arresta il server

### Avvio del Client

Per avviare un client, esegui:
```bash
python client.py
```

Comandi disponibili per il client:
- `@username messaggio`: invia un messaggio privato a un utente specifico
- `broadcast messaggio`: invia un messaggio a tutti gli utenti connessi
- `quit`: esce dal programma

## Funzionalità

- Supporto per messaggi privati
- Supporto per messaggi broadcast
- Logging di tutte le operazioni
- Gestione delle disconnessioni
- Interfaccia colorata per una migliore leggibilità
- Gestione degli errori 