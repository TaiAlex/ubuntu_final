#define TINY_GSM_MODEM_SIM7600 // Định nghĩa model modem
#define MODEM_RST 5
// #define MODEM_PWRKEY 4
#define MODEM_POWER_ON 12
#define MODEM_TX 33
#define MODEM_RX 14
#define MODBUS_DIR_PIN 5  //33 //5
#define MODBUS_RX_PIN 4   //25 //4
#define MODBUS_TX_PIN 16  //26 //16
#define MODBUS_SERIAL_BAUD 9600
#define Mode_reg 2054
#define Pump_st 4168
#define Freq_reg 4169
#define Timer_reg_manual 4136  //D40
#define Sequent_mode 4169      //M32
#define Timer_1_reg_sq 4137    //D41
#define Timer_2_reg_sq 4138    //D42
#include <HardwareSerial.h>
#include <TinyGsmClient.h>
#include <PubSubClient.h>
#include <ModbusMaster.h>
#include <ArduinoJson.h>
#include <esp_system.h>
#include <iostream>
#include <Ticker.h>
#include <cstring>
#include <WiFi.h>
#include <time.h>
#include <math.h>

// Thông tin APN của nhà mạng (Vinaphone)
// const char apn[] = "m3-world"; // APN cho Vinaphone
const char apn[] = "v-internet"; // APN cho Vinaphone
const char user[] = "";        // Thông tin tài khoản (nếu cần)
const char pass[] = "";        // Mật khẩu (nếu cần)

// MQTT Broker Settings
const char* mqtt_broker = "34.126.91.225";
const char* mqtt_username = "admin";
const char* mqtt_password = "admin";
const int mqtt_port = 1883;
const char* mqtt_topics[] = {"/mode", "/motor", "/data", "/threshold", "/inv", "/timespam", "/reset", "/rs", "/wifi", "/err"};
int num_topics = sizeof(mqtt_topics) / sizeof(mqtt_topics[0]), register_quantity = 30;

char jsonBuffer[256], err[256];
StaticJsonDocument<256> motor_st, doc, err_doc;
const char* sensor_name[] = { "CO2 sensor", "Soil sensor", "Full tank sensor", "NH3 sensor", "Soil sensor", "Converter", "Invertor"};
const char* mode_name[] = { "auto", "manual", "sequent", "schedule" };
unsigned long lastTime = 0;
unsigned long previousMillis = 0;
int timerDelay = 30, timer = 0, inv_freq = 0, inv_st = 0;
uint32_t volume = 0;
bool pub_flag;
String mode = "auto";
float upper[3] = { 100.0, 100.0, 200.0 };
float lower[3] = { 0.0, 0.0, 0.0 };
uint8_t pump = 0;
bool active = false;

TinyGsm modem(Serial1);
TinyGsmClient espClient(modem);
PubSubClient mqtt_client(espClient);
ModbusMaster node;

uint8_t* byte_to_bit(uint16_t value) {
  static uint8_t bits[16];  // Thêm "static" để tránh trỏ đến vùng bộ nhớ không hợp lệ
  for (int i = 0; i < 16; ++i) {
    bits[i] = (value >> (15 - i)) & 1;  // Lấy bit thứ i
  }
  return bits;
}

bool sample_period(String start_time, String end_time, int delta) {
  int min = end_time.substring(3, 5).toInt() - start_time.substring(3, 5).toInt();
  int sec = end_time.substring(6, 8).toInt() - start_time.substring(6, 8).toInt();
  int t_delta = min * 60 + sec;
  if (t_delta >= delta) {
    return true;
  }
  return false;
}

void pub(char* topic, char* payload) {
  if (!mqtt_client.connected()) {
    connectToMQTT(mqtt_topics, num_topics);
  }
  mqtt_client.publish(topic, payload);
}

void pub_motorstatus(String mode_st, int freq, int st) {
  char motor_form[512];
  StaticJsonDocument<200> motor_st;
  motor_st["time"] = "23:59:59";
  motor_st["date"] = "2024-11-11";
  // motor_st["time"] = getFormattedTime().time;
  // motor_st["date"] = getFormattedTime().date;
  motor_st["mode"] = mode_st;
  motor_st["inv_freq"] = freq;
  motor_st["inv_st"] = st;
  motor_st["motor"] = (pump == 1) ? true : false;
  serializeJson(motor_st, motor_form);
  if (!mqtt_client.connected()) {
    connectToMQTT(mqtt_topics, num_topics);
  }
  mqtt_client.publish("/motor_ov", motor_form);
}

void modbusPostTransmission() {
  digitalWrite(MODBUS_DIR_PIN, LOW);
  delay(2);
}

float bytesToFloat(uint16_t low, uint16_t high) {
  uint32_t combined = ((uint32_t)high << 16) | low;
  float value;
  memcpy(&value, &combined, 4);
  return value;
}

void setupModem() {
  Serial.begin(115200);
  pinMode(MODEM_POWER_ON, OUTPUT);
  pinMode(MODEM_RST, OUTPUT);
  digitalWrite(MODEM_RST, HIGH);
  delay(10);
  digitalWrite(MODEM_POWER_ON, HIGH);
  DBG("Wait...");
  delay(6000);
  Serial1.begin(115200, SERIAL_8N1, MODEM_RX, MODEM_TX);

  DBG("Initializing modem...");
  if (!modem.restart()) {
    DBG("Failed to restart modem, delaying 10s and retrying");
    return;
  }

  String name = modem.getModemName();
  DBG("Modem Name:", name);

  String modemInfo = modem.getModemInfo();
  DBG("Modem Info:", modemInfo);

  // Khởi động modem
  Serial.println("Initializing modem...");
  modem.restart();

  // Kết nối tới mạng di động
  Serial.println("Connecting to mobile network...");
  if (!modem.waitForNetwork()) {
    Serial.println("Failed to connect to the network");
    while (true);
  }
  Serial.println("Network connected");

  // Cấu hình APN
  Serial.println("Setting APN...");
  if (!modem.gprsConnect(apn, user, pass)) {
    Serial.println("Failed to connect to GPRS");
    while (true);
  }
  Serial.println("GPRS connected");
  DBG("Waiting for network...");
  if (!modem.waitForNetwork(600000L, true)) {
    delay(10000);
    return;
  }

  if (modem.isNetworkConnected()) {
    DBG("Network connected");
    delay(2000);
  }

  DBG("Connecting to", apn);
  if (!modem.gprsConnect(apn, "", "")) {
    delay(10000);
    return;
  }

  bool res = modem.isGprsConnected();
  DBG("GPRS status:", res ? "connected" : "not connected");

  String ccid = modem.getSimCCID();
  DBG("CCID:", ccid);

  String imei = modem.getIMEI();
  DBG("IMEI:", imei);

  String imsi = modem.getIMSI();
  DBG("IMSI:", imsi);

  String cop = modem.getOperator();
  DBG("Operator:", cop);

  IPAddress local = modem.localIP();
  DBG("Local IP:", local);

  int csq = modem.getSignalQuality();
  DBG("Signal quality:", csq);
}

void connectToMQTT(const char* mqtt_topics[], int num_topics) {
  while (!mqtt_client.connected()) {
    String client_id = "ESP32_LTE" + String(modem.getIMEI()); // Sử dụng IMEI của module LTE làm client ID
    Serial.printf("Connecting to MQTT Broker as %s.....\n", client_id.c_str());

    if (mqtt_client.connect(client_id.c_str(), mqtt_username, mqtt_password)) {
      Serial.println("Connected to MQTT broker");

      for (int i = 0; i < num_topics; i++) {
        mqtt_client.subscribe(mqtt_topics[i]);
        Serial.printf("Subscribed to topic: %s\n", mqtt_topics[i]);
      }
    } else {
      Serial.print("Failed, rc=");
      Serial.print(mqtt_client.state());
      Serial.println(" try again in 5 seconds");
      delay(10000);
    }
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.println(topic);
  String context = "";
  for (unsigned int i = 0; i < length; i++) {
    context += ((char)payload[i]);
  }
  Serial.print("Pub Mode: ");
  Serial.println(context);
  // pub("/check", "Received!");
  // Xử lý các topic và hành động tương ứng
  if (String(topic) == "/mode") {
    Serial.println("Toggle mode");
    // mode = context;
    if (context == "auto") {
      uint8_t result;
      result = node.writeSingleCoil(2078, 1);
      if (result == node.ku8MBSuccess) {
        Serial.println("Giá trị đã được ghi thành công!");
      } else {
        Serial.println("Ghi thất bại.");
        pub("/err", "Ghi thất bại.");
      }
    } else if (context == "manual") {
      uint8_t result;
      result = node.writeSingleCoil(2079, 1);
      if (result == node.ku8MBSuccess) {
        Serial.println("Giá trị đã được ghi thành công!");
      } else {
        Serial.println("Ghi thất bại.");
        pub("/err", "Ghi thất bại.");
      }
    } else if (context == "sequent") {
      uint8_t result;
      result = node.writeSingleCoil(2080, 1);
      if (result == node.ku8MBSuccess) {
        Serial.println("Giá trị đã được ghi thành công!");
      } else {
        Serial.println("Ghi thất bại.");
        pub("/err", "Ghi thất bại.");
      }
    } else if (context == "schedule") {
      uint8_t result;
      result = node.writeSingleCoil(2081, 1);
      if (result == node.ku8MBSuccess) {
        Serial.println("Giá trị đã được ghi thành công!");
      } else {
        Serial.println("Ghi thất bại.");
        pub("/err", "Ghi thất bại.");
      }
    }
  }
  if (String(topic) == "/reset") {
    node.writeSingleCoil(2076, 0);
  }
  if (String(topic) == "/rs") {
    mqtt_client.publish("/err", "Received!");
    Serial.println("Restart gateway!");
    esp_restart();
  }
  if (String(topic) == "/motor") {
    StaticJsonDocument<200> ma;
    DeserializationError error_ma = deserializeJson(ma, context);
    if (error_ma) {
      Serial.print(F("deserializeJson() thất bại: "));
      Serial.println(error_ma.f_str());
      return;
    }
    if (ma["mode"] == "manual") {
      Serial.printf("status: %s\n", ma["status"]);
      uint8_t result;
      result = node.writeSingleCoil(2082, (ma["status"] == true) ? 1 : 0);
      if (result == node.ku8MBSuccess) {
        Serial.println("Dieu khien Manual thành công!");
      } else {
        Serial.println("Ghi thất bại.");
      }
    }
    if (ma["mode"] == "sequent") {
      node.writeSingleCoil(2083, 1);
      node.writeSingleCoil(3592, 0);                  //C8
      node.writeSingleCoil(3593, 0);                  //C9
      node.writeSingleRegister(Timer_1_reg_sq, ma["on"]);   //C9
      node.writeSingleRegister(Timer_2_reg_sq, ma["off"]);  //C9
    }
    if (ma["mode"] == "schedule") {
      uint8_t result;
      result = node.writeSingleCoil(1281, (ma["status"] == true) ? 1 : 0);
      if (result == node.ku8MBSuccess) {
        Serial.println("Dieu khien Manual thành công!");
      } else {
        Serial.println("Ghi thất bại.");
      }
    }
  }
  if (String(topic) == "/inv") {
    Serial.println("Topic /inv recieved data!");
    Serial.println(context);
    inv_freq = context.toInt();
    Serial.println(inv_freq);
    uint8_t t1 = node.writeSingleRegister(Freq_reg, inv_freq);
    if (t1 == node.ku8MBSuccess) {
      Serial.println("Ok nha!");
    }
  }
  if (String(topic) == "/timespam") {
    Serial.println("Topic /timespam recieved data!");
    Serial.println(context);
    timerDelay = context.toInt();
    Serial.println(timerDelay);
  }
  if (String(topic) == "/threshold") {
    Serial.println("Topic /theshold recieved data!");
    Serial.println(context);
    StaticJsonDocument<200> doc1;
    DeserializationError error = deserializeJson(doc1, context);
    const char* attribute = doc1["attribute"];
    float up = doc1["upper"];
    float low = doc1["lower"];
    Serial.print("Attribute: ");
    Serial.println(attribute);
    Serial.print("Upper: ");
    Serial.println(up);
    Serial.print("Lower: ");
    Serial.println(low);
    if (strcmp(attribute, "humi") == 0) {
      upper[0] = up;
      lower[0] = low;
      float float_value1 = (float)low;
      float float_value2 = (float)up;
      uint16_t reg1[2];
      uint16_t reg2[2];
      memcpy(reg1, &float_value1, sizeof(float));
      memcpy(reg2, &float_value2, sizeof(float));
      uint8_t result1 = node.writeSingleRegister(4122, reg1[0]);
      uint8_t result2 = node.writeSingleRegister(4123, reg1[1]);
      uint8_t result3 = node.writeSingleRegister(4124, reg2[0]);
      uint8_t result4 = node.writeSingleRegister(4125, reg2[1]);
      if (result1 == node.ku8MBSuccess && result3 == node.ku8MBSuccess) {
        Serial.println("Giá trị đã được ghi thành công!");
      } else {
        Serial.println("Ghi thất bại.");
      }
    }
    if (strcmp(attribute, "temp") == 0) {
      Serial.print("temp: ");
      upper[1] = up;
      lower[1] = low;
    }
    if (strcmp(attribute, "ec") == 0) {
      upper[2] = up;
      lower[2] = low;
    }
  }
  Serial.println("\n-----------------------");
}

void modbusPreTransmission() {
  delay(2);
  digitalWrite(MODBUS_DIR_PIN, HIGH);
}

void setup() {
  setupModem();
  mqtt_client.setServer("34.126.91.225", 1883);
  mqtt_client.setKeepAlive(60);
  mqtt_client.setCallback(mqttCallback);
  connectToMQTT(mqtt_topics, num_topics);
  pinMode(MODBUS_DIR_PIN, OUTPUT);
  digitalWrite(MODBUS_DIR_PIN, LOW);
  Serial2.begin(MODBUS_SERIAL_BAUD, SERIAL_8N1, MODBUS_RX_PIN, MODBUS_TX_PIN);
  Serial2.setTimeout(100);
  node.begin(5, Serial2);
  node.preTransmission(modbusPreTransmission);
  node.postTransmission(modbusPostTransmission);
  ticker.attach(1.0, blink);
  // currentDateTime = getFormattedTime();
  // current_time = currentDateTime.time;
  // Serial.print("Setup Time: ");
  // Serial.println(current_time);
}

void loop() {
  unsigned long currentMillis = millis();
  uint8_t result;
  uint16_t CO2_value, empty_tank, full_tank, flow_value, temp, data[register_quantity];
  float temp_value, humi_value, EC_value, salt_value, TDS_value, pressure_value, values[5], airtemp, airhumi;
  if (!mqtt_client.connected()) {
    connectToMQTT(mqtt_topics, num_topics);
  }
  mqtt_client.loop();
  result = node.readHoldingRegisters(4146, register_quantity);
  
  node.writeSingleRegister(4596, 0);
  if (result == node.ku8MBSuccess) {
    for (int j = 0; j < register_quantity; j++) {
      data[j] = node.getResponseBuffer(j);
    }
    node.writeSingleRegister(4296, 1);
  }
  CO2_value = data[0];
  airhumi = data[10]/10;
  airtemp = data[11]/10;
  humi_value = bytesToFloat(data[2], data[3]);
  temp_value = bytesToFloat(data[4], data[5]);
  EC_value = bytesToFloat(data[6], data[7]);
  salt_value = bytesToFloat(data[12], data[13]);
  TDS_value = bytesToFloat(data[14], data[15]);
  pressure_value = bytesToFloat(data[16], data[17]);
  full_tank = data[8];
  inv_freq = data[23];
  inv_st = data[22];
  String mode_sd;
  for (int i_m = 0; i_m < 4; i_m++) {
    if (byte_to_bit(data[28])[15 - i_m] == 1) {
      // Serial.printf("K2M30: %d\n", data[28]);
      mode_sd = mode_name[i_m];
    }
  }
  flow_value = data[27];
  if (mode_sd != mode) {
    // Serial.printf("Mode: %s\n", mode);
    mode = mode_sd;
    pub_motorstatus(mode, inv_freq, inv_st);
  }
  if (byte_to_bit(data[26])[14] != pump) {
    pump = byte_to_bit(data[26])[14];
    pub_motorstatus(mode, inv_freq, inv_st);
  }
  if (((uint32_t)data[19] << 16) | data[18] > 0) {
    volume = ((uint32_t)data[19] << 16) | data[18];
    pub_flag = true;
  }
  if ((flow_value == 0) && (pub_flag)) {
    if (!mqtt_client.connected()) {
      connectToMQTT(mqtt_topics, num_topics);
    }
    String payload = "{\"date\":\"2024-11-20\","
      "\"time\":\"23:59:59\","
      "\"volume\":" + String(volume) + "}";
    mqtt_client.publish("/vol", payload.c_str());
    pub_flag = false;
  }
  // Serial.println(data[28]);
  for (int i_m = 0; i_m < 4; i_m++) {
    if (byte_to_bit(data[28])[15 - i_m] == 1) {
      mode = mode_name[i_m];
    }
  }
  pump = byte_to_bit(data[26])[14];
  // Serial.print("Time: "); Serial.println(currentDateTime.time);
  // if (sample_period(current_time, currentDateTime.time, timerDelay)) {


  if (currentMillis - previousMillis >= timerDelay*1000) {
    previousMillis = currentMillis;
    Serial.printf("K2M30: %d\n", data[29]);
    StaticJsonDocument<10> doc;
    for(int i_err = 0; i_err < 7; i_err++) {
      if (byte_to_bit(data[29])[15 - i_err] == 1) {
        char *key = new char[4];
        sprintf(key, "err%d",i_err+1);
        err_doc[key] = sensor_name[i_err];
        Serial.println(sensor_name[i_err]);
        node.writeSingleCoil(3584 + i_err, 0);
      }
    }
    serializeJson(err_doc, err);
    if (!mqtt_client.connected()) {
      connectToMQTT(mqtt_topics, num_topics);
    }
    mqtt_client.publish("/err", err);
    err[0] = '\0';
    float temp_celsius = temperatureRead();
    char temperature[10];
    sprintf(temperature, "%.2f", temp_celsius);
    // current_time = currentDateTime.time;
    // Serial.print("Time: "); Serial.println(current_time);
    // doc["time"] = currentDateTime.time;
    // doc["date"] = currentDateTime.date;
    doc["CO2"] = CO2_value;
    doc["Temp"] = temp_value;
    doc["Humi"] = humi_value;
    doc["EC"] = EC_value;
    doc["Salt"] = salt_value;
    doc["Pressure"] = pressure_value;
    doc["AirTemp"] = airtemp;
    doc["AirHumi"] = airhumi;
    doc["Full"] = full_tank;
    doc["flow"] = flow_value;


    doc["time"] = "23:59:59";
    doc["date"] = "2024-11-11";
    // doc["flow"] = (float)random(1900)/1.00;
    // doc["CO2"] = random(2000);
    // doc["Temp"] = (float)random(25,30)/1.10;
    // doc["Humi"] = (float)random(90,93)/1.40;
    // doc["EC"] = (float)random(100,120)/1.30;
    // doc["Salt"] = (float)random(190,220)/1.20;
    // doc["Pressure"] = (float)random(0,6)/1.40;
    // doc["AirTemp"] = (float)random(25,30)/1.04;
    // doc["AirHumi"] = (float)random(90,93)/1.01;
    // doc["Full"] = full_tank;
    serializeJson(doc, jsonBuffer);
    if (!mqtt_client.connected()) {
      connectToMQTT(mqtt_topics, num_topics);
    }
    active = mqtt_client.publish("/data", jsonBuffer);
    if(active) {
      node.writeSingleRegister(4596, 1);
    }
    mqtt_client.publish("/err", temperature);
  }
}
