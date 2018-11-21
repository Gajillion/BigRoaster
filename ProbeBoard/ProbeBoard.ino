#include <ESP8266HTTPClient.h>
#include <ESP8266WiFi.h>

#include <Wire.h>
#include <SPI.h>
#include <Adafruit_LIS3DH.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_MAX31855.h>
#include <ArduinoJson.h>

#include <math.h>
#include <TimeLib.h>

// Use software SPI
#define SPI_CLK 14
#define SPI_MISO 12
#define SPI_MOSI 13

#define LIS3DH_CS 16 // PCB wired

#define NUM_TCS 4
#define MAX31855_CS1 5
#define MAX31855_CS2 4
#define MAX31855_CS3 0
#define MAX31855_CS4 2

// software SPI
Adafruit_LIS3DH lis = Adafruit_LIS3DH(LIS3DH_CS, SPI_MOSI, SPI_MISO, SPI_CLK);

Adafruit_MAX31855 *tcs[NUM_TCS] = {
  new Adafruit_MAX31855(SPI_CLK, MAX31855_CS1, SPI_MISO),
  new Adafruit_MAX31855(SPI_CLK, MAX31855_CS2, SPI_MISO),
  new Adafruit_MAX31855(SPI_CLK, MAX31855_CS3, SPI_MISO),
  new Adafruit_MAX31855(SPI_CLK, MAX31855_CS4, SPI_MISO)
};

const char* ssid     = "roasto";
const char* password = "Password";
HTTPClient http;

int sampleRate = 5000; // Delay in ms between loops
int checkInRate = 10; // How many times through the loop before we check in for a new sampleRate?
int checkInCount;
unsigned long t = millis();

void checkIn()
{
  const size_t bufferSize = JSON_OBJECT_SIZE(2) + 40;
  DynamicJsonBuffer jsonBuffer(bufferSize);

  http.begin("http://192.168.4.1:5000/checkin");
  int httpCode = http.GET();
  // httpCode will be negative on error
  if (httpCode > 0) {
    if (httpCode == HTTP_CODE_OK) {
      String payload = http.getString();
      checkInCount = 0;
      Serial.println(payload);
      JsonObject& root = jsonBuffer.parseObject(payload);

      checkInRate = int(root["checkInRate"]);
      sampleRate = int(root["sampleRate"]);

      Serial.print("checkInRate: "); Serial.print(checkInRate); Serial.print(" sampleRate: "); Serial.println(sampleRate);
    }
  }

}

void WiFi_Connect()
{
  WiFi.disconnect();
  WiFi.mode(WIFI_STA);
  WiFi.hostname("tempprobe"); // https://github.com/esp8266/Arduino/issues/2826
  WiFi.begin(ssid, password);

  // Wait for connection
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("Connected to ");
  Serial.println(ssid);
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  Serial.println(WiFi.macAddress());
}

void setup(void) {
  Serial.begin(115200);

  if (! lis.begin(0x18)) {   // change this to 0x19 for alternative i2c address
    Serial.println("LIS3DH not found. Exiting.");
    while (1);  // halt right here
  }
  Serial.println("LIS3DH found!");

  lis.setRange(LIS3DH_RANGE_2_G);   // 2G

  Serial.print("Range = "); Serial.print(2 << lis.getRange());
  Serial.println("G");

  // Set our pins
  pinMode(LIS3DH_CS, OUTPUT);
  digitalWrite(LIS3DH_CS, HIGH);
  pinMode(MAX31855_CS1, OUTPUT);
  digitalWrite(MAX31855_CS1, HIGH);
  pinMode(MAX31855_CS2, OUTPUT);
  digitalWrite(MAX31855_CS2, HIGH);
  pinMode(MAX31855_CS3, OUTPUT);
  digitalWrite(MAX31855_CS3, HIGH);
  pinMode(MAX31855_CS4, OUTPUT);
  digitalWrite(MAX31855_CS4, HIGH);

  // Start up the wifi
  WiFi_Connect();

  // allow reuse (if server supports it)
  http.setReuse(true);

  // Set up our thermocouples.
  for (int i = 0; i < NUM_TCS; i++) {
    tcs[i]->readInternal();
    // If this call fails, there is no thermocouple listening
    if (tcs[i]->readCelsius() == 0.00 ) {
      Serial.println("deleting tcs[" + String(i) + "]");
      delete tcs[i];
      tcs[i] = NULL;
    }
  }

  checkIn();
}

void loop() {
  lis.read();      // get X Y and Z data at once
  if (WiFi.status() == WL_CONNECTED) {
    // See if we have any status updates
    if (checkInCount > checkInRate) {
      checkIn();
    }
    checkInCount++;

    const size_t bufferSize = JSON_ARRAY_SIZE(4) + JSON_OBJECT_SIZE(2) + 4*JSON_OBJECT_SIZE(3) + JSON_OBJECT_SIZE(4) + 230; // https://arduinojson.org/v5/assistant/
    DynamicJsonBuffer jsonBuffer(bufferSize);
    JsonObject& root = jsonBuffer.createObject();

    JsonObject& position = root.createNestedObject("position");
    position["x"] = lis.x;
    position["y"] = lis.y;
    position["z"] = lis.z;

    // https://theccontinuum.com/2012/09/24/arduino-imu-pitch-roll-from-accelerometer/

    const float alpha = 0.5;
    double fXg = 0;
    double fYg = 0;
    double fZg = 0;

    double pitch, roll;

    //Low Pass Filter
    fXg = lis.x * alpha + (fXg * (1.0 - alpha));
    fYg = lis.y * alpha + (fYg * (1.0 - alpha));
    fZg = lis.z * alpha + (fZg * (1.0 - alpha));

    //Roll & Pitch Equations
    // We don't need pitch if we're mounted correctly
    // pitch = (atan2(fXg, sqrt(fYg*fYg + fZg*fZg))*180.0)/M_PI;
    
    roll  = (atan2(-fYg, fZg) * 180.0) / M_PI;
    if(roll < 0){
      roll += 360;
    }

    // And deliver in radians
    roll *= (M_PI/180.0);
    // round off to the nearest hundredths of a radian
    roll *= 100;
    roll = round(roll);
    roll /= 100;
    
    position["rotation"] = roll;
    JsonArray& probes = root.createNestedArray("probes");

    // Now, add in our thermocouples
    for (int i = 0; i < NUM_TCS; i++){
      if (tcs[i] != NULL) {
        double c = tcs[i]->readCelsius();
        if (c != 0.00) {
          JsonObject& tc_probe = probes.createNestedObject();
          tc_probe["number"] = i + 1;
          tc_probe["temp"] = c;
          tc_probe["elapsed"] = millis() - t;
        }
      }
    }

    char buf[bufferSize + 1];
    root.prettyPrintTo(buf, sizeof(buf));
    Serial.println(buf);

    http.begin("http://192.168.4.1:5000/postsensors");
    http.addHeader("Content-Type", "application/json");

    int httpCode = http.POST(buf); //Send the request
    String payload = http.getString(); //Get the response payload
    Serial.println(httpCode); //Print HTTP return code
    Serial.println(payload); //Print request response payload
    http.end(); //Close connection
  }
  else {
    WiFi_Connect();
  }
  t = millis();
  delay(sampleRate);
}
