# REST-API-Task-Manager

A simple REST API for managing tasks, built with Python's standard library and SQLite.

## Features

- Create, read, update, and delete tasks
- Mark tasks as completed
- Filter tasks by completion status
- Persistent SQLite storage
- Automated API tests

## Quick start

```bash
python app/main.py
```

API runs at `http://127.0.0.1:8000`.

## Endpoints

- `GET /` – health check
- `POST /tasks` – create a task
- `GET /tasks` – list tasks (`?completed=true|false` optional)
- `GET /tasks/{task_id}` – fetch one task
- `PUT /tasks/{task_id}` – update one task
- `PATCH /tasks/{task_id}/complete` – mark complete
- `DELETE /tasks/{task_id}` – delete task

## Run tests

```bash
python -m unittest -v
```
