# from router import *
from fastapi import Depends, FastAPI, HTTPException, status, File, UploadFile, Form, APIRouter, Request
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta, timezone
from pyexcel.cookbook import merge_all_to_a_book
from jwt.exceptions import InvalidTokenError
from starlette.responses import JSONResponse
from passlib.context import CryptContext
from pymongo import MongoClient
from datetime import datetime
from .models.models import *
# from subrouter import *
import pandas as pd
import random
import time
import glob
import pytz
import jwt
import os

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 31
client = MongoClient("mongodb://0.0.0.0:27017/")
db = client["mydatabase"]
user_mongo = db["user"]
sensor = db["sensor"]
motor_db = db["motor"]
print("motor collection created!")
print("Tập collection: ", db.list_collection_names())
crop = db["crop"]
login = db["login"]
print("Tập collection: ", db.list_collection_names())

conf = ConnectionConfig(
    MAIL_USERNAME ="truc8400@gmail.com",
    MAIL_PASSWORD = "wwsy korg temm sinv",
    MAIL_FROM = "truc8400@gmail.com",
    MAIL_PORT = 587,
    MAIL_SERVER = "smtp.gmail.com",
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

html = """<p>Thanks for using My Product</p>"""
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
route = APIRouter()

def check_id(collection: str):
    col = db[collection]
    _id = col.count_documents({})
    return int(_id + 1)
    
def read_db(col_name: str, number: int = None):
    col_list = db.list_collection_names()
    if col_name in col_list:
        col = db[col_name]
        # print(f"Has been exists {str(col)} collection")
        n_max = col.count_documents({})
        print(n_max)
        if n_max == 0:
            print("Đây nè")
            return None
        if number is None:
            # print("Not number")
            return col
        elif number == 0:
            # print("== number")
            data = list(col.find().sort("_id"))
        elif number > n_max:
            # print("> number")
            data = list(col.find().sort("_id", -1).limit(n_max))
        else:
            # print("else")
            data = list(col.find().sort("_id", -1).limit(number))
        return data
    
def user_db():
    user_dict = {}
    usrs = list(user_mongo.find().sort("_id"))
    for usr in usrs:
        username = usr['username']
        user_dict[username] = {
            'username': usr['username'],
            'full_name': usr['full_name'],
            'email': usr['email'],
            'hashed_password': usr['hashed_password'],
            'role': usr['role'],
            'phone': usr['phone'],
            'lastlogin': usr['lastlogin'],
            'disabled': usr['disabled']
        }
    return user_dict

def gettime():
    timezone = pytz.timezone("Asia/Ho_Chi_Minh")
    current_time = datetime.now(timezone)
    date = current_time.strftime("%Y-%m-%d")
    time = current_time.strftime("%H:%M:%S")
    # print("Thời gian hiện tại ở múi giờ Asia/Ho_Chi_Minh:", date, time)
    return date, time
    
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def authenticate_user(db, username: str, password = None, admin_verifi = None):
    usr = get_user(db, username)
    if not (usr or verify_password(password, usr.hashed_password)):
        # print("verify_password: ",verify_password(password, usr.hashed_password))
        print("401 ở đây auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if admin_verifi:
        if not usr.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have admin privileges",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return usr

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    timezone = pytz.timezone("Asia/Ho_Chi_Minh")
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone) + expires_delta
    else:
        expire = datetime.now(timezone) + timedelta(minutes=15)
    print("expire: ",expire)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print("payload: ", payload)
        username: str = payload.get("sub")
        if username is None:
            print("401 ở đây get current user username is None")
            raise credentials_exception
        token_data = TokenData(username=username)
        print("token_data: ", token_data)
    except InvalidTokenError as e:
        print("401 ở đây get current user except", e)
        raise credentials_exception
    user = get_user(user_db(), username=token_data.username)
    # print("user: ", user)
    if user is None:
        print("401 ở đây get current user is None")
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

default_user = {
    "tai": {
        "_id": 1,
        "username": "tai",
        "full_name": "Vu Van Tai",
        "email": "alextaivu@gmail.com",
        "hashed_password": get_password_hash("tai"),
        "role": "admin",
        "phone": "01274906435",
        "lastlogin": "None",
        "disabled": "False"
    },
    "truc": {
        "_id": 2,
        "username": "truc",
        "full_name": "Do Thanh Truc",
        "email": "truc8400@gmail.com",
        "hashed_password": get_password_hash("truc"),
        "role": "user",
        "phone": "0948367264",
        "lastlogin": "None",
        "disabled": "False"
    }
}

if user_mongo.count_documents({}) == 0:
    for user_data in default_user.values():
        # Chỉ lấy dữ liệu cần thiết
        user = {
            "_id": user_data["_id"],
            "username": user_data["username"],
            "full_name": user_data["full_name"],
            "email": user_data["email"],
            "hashed_password": user_data["hashed_password"],
            "role": user_data["role"],
            "phone": user_data["phone"],
            "lastlogin": user_data["lastlogin"],
            "disabled": user_data["disabled"]
        }
        user_mongo.insert_one(user)
        
# @route.get("/api/{col}/{n}")
# async def get_data(col: str, n: int, current_user: User = Depends(get_current_active_user)):
#     if col == "data" :
#         data_db = read_db("sensor", n)
#     elif col == "motor":
#         data_db = read_db("motor", n)
#     elif col == "user":
#         data_db = read_db("user", n)
#     elif col in db.list_collection_names():
#         data_db = read_db(f"{col}", n)
#     return data_db
        
@route.get("/api/{col}/{n}")
async def get_data(col: str, n: int):
    print("list collection: ",db.list_collection_names())
    if col == "data" :
        data_db = read_db("sensor", n)
    else:
        print("Data type: ", type(col))
        data_db = read_db(col,n)
    # print("Data type collection: ", (data_db))
    return data_db
