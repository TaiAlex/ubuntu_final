import paho.mqtt.publish as publish

from .auth import *
import json
# crop = db["crop"]
# login = db["login"]
# user_mongo = db["user"]
# sensor = db["sensor"]
# motor = db["motor"]
auth_mqtt = {"username": "tai", "password": "tai"}
dialog = pd.read_csv(r'~/server/routers/diary.csv', header = None, index_col = False)
# df = pd.DataFrame(dialog)
system_mode = False
motor = [False, False, False]
days = read_db("crop", 1)
if days is not None:
    days = read_db("crop", 1)[0].get("days")
lower = 0
upper = 100
freq_inv = 0
timespam_gw = 0

def pub(topic, payload):
    publish.single(topic, payload, hostname="0.0.0.0", auth=auth_mqtt)

def get_stage(end_date: str):
    date,_ = gettime()
    str_now = datetime.strptime(date, "%Y-%m-%d")
    days = (str_now - end_date).days
    data = list(dialog.iloc[days])
    data[0] = int(data[0])
    return data

@route.post("/token")
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(),) -> Token:
    client_host = request.client.host
    print("client_host: ", client_host)
    user = authenticate_user(user_db(), form_data.username, form_data.password)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    print("ACCESS_TOKEN_EXPIRE_MINUTES: ", ACCESS_TOKEN_EXPIRE_MINUTES)
    print("access_token_expires: ", access_token_expires)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    date, stime = gettime()
    data1 = {
        "_id": check_id("login"),
        "date": date,
        "time": stime,
        "username": user.username,
        "token": access_token
    }
    login.insert_one(data1)
    user_mongo.update_one({'username':user.username}, {"$set": {"lastlogin":f"{date} {stime}"}})
    print("data: ", data1)
    return Token(access_token=access_token, token_type="bearer")

@route.post("/signup")
async def create_account(form_data: RegisterForm):
    print("form_data: ", form_data)
    authenticate_user(user_db(), form_data.masterusr, form_data.masterpwd, True)
    new_user = get_user(user_db(), form_data.username)
    if new_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    user_form = {
        '_id': check_id("user"),
        'username': form_data.username,
        'full_name': form_data.full_name,
        'email': form_data.email,
        'hashed_password': get_password_hash(form_data.password),
        'role': form_data.role,
        'phone': form_data.phone,
        'lastlogin': "None",
        'disabled': False
    }
    user_mongo.insert_one(user_form)
    return {"Detail": "Create account successfully"}

@route.get("/users/me/", response_model=User_info)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    # authenticate_user()
    print("current_user: ", current_user.role)
    return {
        "full_name": current_user.full_name,
        "role": current_user.role
    }

@route.get("/predict")
async def get_predict(current_user: User = Depends(get_current_active_user)):
    global days, stage
    print("Days: ", days)
    # print("Data: ", pd.series(dialog.iloc[a]))
    data = list(dialog.iloc[days])
    data[0] = int(data[0])
    data_dict = {
        "days": data[0],
        "stage": data[1],
        "advices": data[2]
    }
    print("Data_dict: ", data_dict)
    return data_dict

@route.post("/control_mode")
async def post_mode(mode_ctl: Mode):
    global system_mode, motor
    # authenticate_user()
    system_mode = mode_ctl.mode
    pub("/mode",system_mode)
    return 0

@route.get("/control_mode")
async def get_mode():
    global system_mode
    return {"system_mode": system_mode}

@route.post("/motor/{n}")
async def post_motor(n: int, st: Motor, current_user: User = Depends(get_current_active_user)):
    authenticate_user(user_db(), current_user.username, None, True)
    global system_mode
    date, stime = gettime()
    if not st.status:
        off_time = stime
        print("off time: ", stime)
    motor[n-1] = bool(st.status)
    print(f"Motor {n-1}: {motor[n-1]}")
    data = {
        "_id": check_id("motor"),
        "time": stime,
        "date": date,
        "mode": system_mode,
        "motor1": motor[0],
        "motor2": motor[1],
        "motor3": motor[2]
    }
    motor_db.insert_one(data)
    pub(f"/motor{n}", motor[n-1])
    return {"Detail": f"Status pump {n}: {st.status}"}

@route.post("/motor")
async def post_motor(form: motor_form):
    data = {
        "_id": check_id("motor"),
        "time": form.time,
        "date": form.date,
        "mode": form.mode,
        "motor1": form.motor1,
        "motor2": form.motor2,
        "motor3": form.motor3
    }
    motor_db.insert_one(data)
    return {"Detail": "Ok nha"}

# @route.get("/api/{col}/{n}")
# async def get_data(col: str, n: int, current_user: User = Depends(get_current_active_user)):
#     print("Alo alo: ", current_user)
#     print("Ok luốn")
#     if col == "data":
#         print(type(read_db("sensor", n)))
#         data = read_db("sensor", n)
#     elif col == "motor":
#         data = read_db("motor", n)
#     elif col == "user":
#         data = read_db("user", n)
#     return data

@route.post("/api/v2/{n}")
async def create_virtual_data(n: int):
    for i in range(n):
        date, stime = gettime()
        data = {
            "_id": check_id("sensor"),
            "date": date,
            "time": stime,
            "CO2": random.randint(500,1200),
            "Temp": random.randint(20,25),
            "Humi": random.randint(60,95),
            "EC": random.randint(20,25),
            "pH": random.randint(20,25),
            "Pressure": random.randint(20,25),
            "Flowmeters": random.randint(20,25),
            "WaterlevelSensor1": random.choice([True, False]),
            "WaterlevelSensor2": random.choice([True, False]),
            "Waterpumped": random.randint(0, 100),
            "device_name": "Truc Farm"
        }
        print("check_id: sensor",  check_id("sensor"))
        sensor.insert_one(data)
        data1 = {
            "_id": check_id("motor"),
            "time": stime,
            "date": date,
            "mode": random.choice([True, False]),
            "motor1": random.choice([True, False]),
            "motor2": random.choice([True, False]),
            "motor3": random.choice([True, False])
        }
        motor_db.insert_one(data1)
        time.sleep(3)
    return {"Detail": data}

@route.post("/api/v1")
async def gateway_data(form: FormData):
    date, stime = gettime()
    data = {
        "_id": check_id("sensor"),
        "date": date,
        "time": stime,
        "CO2": form.CO2,
        "Temp": form.Temp,
        "Humi": form.Humi,
        "EC": form.EC,
        "pH": form.pH,
        "Pressure": form.Pressure,
        "Flowmeters": form.Flowmeters,
        "WaterlevelSensor1": form.ls1,
        "WaterlevelSensor2": form.ls2,
        "Waterpumped": form.wp,
        "device_name": "Truc Farm"
    }
    sensor.insert_one(data)
    return {"Detail": "Ok nhó"}

@route.post("/crop")
async def post_crop(crop_data: crop_info, usr: Verify_ad):
    authenticate_user(user_db(), usr.masterusr, usr.masterpwd, True)
    date, stime = gettime()
    global days
    str_date = datetime.strptime(crop_data.startdate, "%Y-%m-%d")
    str_now = datetime.strptime(date, "%Y-%m-%d")
    days = (str_now - str_date).days
    end_date = str_date + timedelta(days=75)
    data = {
        "_id": check_id("crop"),
        "date": date,
        "time": stime,
        "project": crop_data.project,
        "startdate": crop_data.startdate,
        "days": days,
        "harvestdate": end_date.strftime("%Y-%m-%d"),
        "stage": get_stage(str_date)[1],
        "quantity": crop_data.quantity,
        "area": crop_data.area
    }
    crop.insert_one(data)
    return {"Message": "POST OK"}

@route.get("/crop")
async def get_crop():
    data = read_db("crop", 1)
    return data

@route.post("/export-file/{i}")
async def send_file(i: str, admin: Verify_ad, current_user: User = Depends(get_current_active_user)) -> JSONResponse:
    usr = authenticate_user(user_db(), admin.masterusr, admin.masterpwd, True)
    if i == "data":
        i = "sensor"
    col = read_db(i)
    print(type(col))
    cursor = list(col.find({}, {"hashed_password": 0}))
    df = pd.DataFrame(cursor)
    directory = 'server/storages'
    if not os.path.exists(directory):
        os.makedirs(directory)
    csv_path = os.path.join(directory, 'export_data.csv')
    excel_path = os.path.join(directory, 'export_data.xlsx')
    df.to_csv(csv_path, index=False)
    merge_all_to_a_book(glob.glob(csv_path), excel_path)
    message = MessageSchema(
        subject="Fastapi mail module",
        recipients=[usr.email],
        body=html,
        subtype=MessageType.html,
        attachments=[excel_path]
    )
    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        return JSONResponse(status_code=200, content={"message": "email has been sent"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

@route.post("/upload-img")
async def upload_file(file: UploadFile = File(...), username: str = Form(...)):
    if not os.path.exists("./user"):
        os.makedirs("./user")
    file_path = os.path.join("./user", f"{username}.jpg")
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    return JSONResponse(content={"message": "Image uploaded successfully", "filePath": file_path})

@route.get("/test")
async def test():
    global client
    user = read_db("user", 0)
    sensor = read_db("sensor", 0)
    print(db.list_collection_names())
    return user, sensor

@route.get("/del/{collection}")
async def read_own_items(collection: str):
    col_list = db.list_collection_names()
    print("Collection exists: ", col_list)
    if collection in col_list:
        col = read_db(collection)
        col.drop()
        return {"Detail": "Dropped!"}
    return {"Ok": "OK"}

@route.patch("/users/{method}/{usr}")
async def edit_info(method: str, usr: str, updated_data, ad: Verify_ad):
    authenticate_user(user_db(), ad.masterusr, ad.masterpwd, True)
    usr_obj = user_mongo.find_one({"username": usr})
    keys = list(usr_obj.keys())
    if method == "delete":
        user_mongo.delete_one({"username": usr})
        return {"status": "user was deleted!"}
    elif method == "password":
         method = "hashed_password"
         updated_data = get_password_hash(updated_data)
    if method not in keys:
        raise HTTPException(status_code=400, detail="Don't have field for this collection!")
        # return {"Detail": "You don't have permission"}
    print("ok at here!")
    print("ok at here!", usr)
    user_mongo.update_one({"username": usr}, {"$set": {method: updated_data}})
    return {"status": f"{method} changed!"}

@route.post("/threshold/{attr}")
async def post_threshold(attr: str, cond: Threshold, current_user: User = Depends(get_current_active_user)):
    authenticate_user(user_db(), current_user.username, None, True)
    global lower, upper
    lower = cond.lower
    upper = cond.upper
    print("lower: ", lower, "upper: ", upper)
    cond = cond.dict()
    data = json.dumps(cond)
    pub("/threshold", data)
    return data

@route.get("/threshold/{attr}")
async def get_threshold(attr: str, current_user: User = Depends(get_current_active_user)):
    global lower, upper
    return {
        "lower": lower,
        "upper": upper
    }

@route.get("/pumped/{n}")
async def get_vol(n: int, current_user: User = Depends(get_current_active_user)):
    return True
    
@route.post("/inv/{freq}")
# async def post_freq(freq: int):
async def post_freq(freq: int, current_user: User = Depends(get_current_active_user)):
    authenticate_user(user_db(), current_user.username, None, True)
    global freq_inv
    freq_inv = freq * 100
    pub("/inv", freq_inv)
    return {"message": "Post frequency for inverter successful!"}
    
@route.get("/inv")
async def get_freq(current_user: User = Depends(get_current_active_user)):
    return freq_inv/100


@route.post("/spam/{tsp}")
async def post_freq(tsp: int, current_user: User = Depends(get_current_active_user)):
    authenticate_user(user_db(), current_user.username, None, True)
    pub("/timespam", tsp)
    return {"message": "Set time spam for gateway successful!"}

# Lượng nước

