from typing import Optional, List
from pydantic import BaseModel, EmailStr
from typing import Union

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Union[str, None] = None

class User(BaseModel):
    username: Union[str, None] = None
    email: Union[str, None] = None
    role: str
    full_name: str
    phone: Union[str, None] = None
    disabled: Union[bool, None] = None

class UserInDB(User):
    hashed_password: str

class RegisterForm(BaseModel):
    full_name: str
    username: str
    password: str
    role: str
    email: str
    phone: str
    masterusr: str
    masterpwd: str
    # disabled: Union[bool, None] = None

class Mode(BaseModel):
    mode: bool

class FormData(BaseModel):
    date: str
    time: str
    CO2: int
    Temp: float
    Humi: float
    EC: float
    pH: float
    Pressure: float
    Flowmeters: float
    ls1: bool
    ls2: bool
    wp: float
    # Motor1: bool
    # Motor2: bool
    # Motor3: bool
    # device_name: str

class control_status(BaseModel):
    Mode: str
    Parameter: str

class motor_form(BaseModel):
    time: str
    date: str
    mode: bool
    motor1: bool
    motor2: bool
    motor3: bool

class EmailSchema(BaseModel):
    email: List[EmailStr]
    
class Motor(BaseModel):
    # name: str
    status: bool
    
class Verify_ad(BaseModel):
    masterusr: str
    masterpwd: str
    
class User_info(BaseModel):
    full_name: str
    role: str
    
class crop_info(BaseModel):
    project: str
    startdate: str
    quantity: int
    area: int
    
class Threshold(BaseModel):
    attribute: str
    upper: float
    lower: float
