# FastAPI Basics

FastAPI is a Python web framework used to build APIs quickly.

## Why it's used in portfolio projects
- simple routing (`@app.get`, `@app.post`)
- built-in data validation with Pydantic models
- works well with async features and WebSockets

## Typical structure
- `app = FastAPI()`
- define request/response models
- create endpoints for your UI to call

## WebSocket idea
With a WebSocket endpoint, your UI can receive partial updates (streaming).
This can make responses feel faster and more interactive.
