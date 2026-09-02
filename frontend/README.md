# FlowMate frontend

React + Vite dashboard for FlowMate. Reads the FastAPI backend's `/scan/latest` (cached agent
output -- never triggers a live scan) and `/standups/{engineer}` endpoints; talks to no other
service directly.

## Run locally

```bash
npm install
npm run dev          # http://localhost:5173, expects the API at http://localhost:8000
```

Set `VITE_API_BASE_URL` in a `.env.local` (see `.env.example`) if the API runs elsewhere.

## Build

```bash
npm run build         # outputs to dist/
```
