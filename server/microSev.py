from fastapi import FastAPI, Form, Request, HTTPException, status
# from routers.router import *
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from routers import auth
import uvicorn

app = FastAPI()

origins = [
    "http://0.0.0.0.tiangolo.com",
    "https://0.0.0.0/.tiangolo.com",
    "http://0.0.0.0.tiangolo.com",
    "https://0.0.0.0/.tiangolo.com",
    "http://34.87.151.244",
    "http://192.168.1.13",
    "http://18.138.48.98:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return "Wellcome to my web"

@app.get("/test")
async def read_root(request: Request):
    client_host = request.client.host
    return {"client_ip": client_host}

app.include_router(auth.route)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=2002)