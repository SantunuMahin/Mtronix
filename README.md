# Mtronix

Django inventory and sales MVP with products, suppliers, stock tracking, purchases, sales, and a starter dashboard.

## Setup

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

## PostgreSQL

SQLite is used by default for local development. To use PostgreSQL, set these variables before running migrations:

```powershell
$env:POSTGRES_DB='mtronix'
$env:POSTGRES_USER='postgres'
$env:POSTGRES_PASSWORD='password'
$env:POSTGRES_HOST='localhost'
$env:POSTGRES_PORT='5432'
```
