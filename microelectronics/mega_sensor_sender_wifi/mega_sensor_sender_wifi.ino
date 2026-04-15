#include <Adafruit_SCD30.h>
#include <Wire.h>

#define FRAME_LEN 12

Adafruit_SCD30 scd30;
uint8_t gasFrame[FRAME_LEN];

struct SCD30Data {
  float temperature;
  float humidity;
  float co2;
  bool valid;
};

struct GasData {
  float o2;
  int co;
  float h2s;
  float ch4;
  bool valid;
};

SCD30Data scdData = {0, 0, 0, false};
GasData gasData = {0, 0, 0, 0, false};

bool scd30Ready = false;
unsigned long lastSendMs = 0;
const unsigned long sendIntervalMs = 200;

bool readSensorFrame(uint8_t *buf) {
  while (Serial1.available()) {
    if (Serial1.peek() == 0x3C) {
      break;
    }
    Serial1.read();
  }

  if (Serial1.available() < FRAME_LEN) {
    return false;
  }

  for (int i = 0; i < FRAME_LEN; i++) {
    buf[i] = Serial1.read();
  }

  return true;
}

bool checkChecksum(const uint8_t *buf) {
  uint8_t sum = 0;
  for (int i = 0; i <= 10; i++) {
    sum += buf[i];
  }
  return (sum == buf[11]);
}

void updateSCD30() {
  if (!scd30Ready) return;
  if (!scd30.dataReady()) return;

  if (scd30.read()) {
    scdData.temperature = scd30.temperature;
    scdData.humidity = scd30.relative_humidity;
    scdData.co2 = scd30.CO2;
    scdData.valid = true;
  } else {
    scdData.valid = false;
  }
}

void updateGasSensor() {
  if (!readSensorFrame(gasFrame)) return;

  if (gasFrame[0] != 0x3C || gasFrame[1] != 0x04) {
    gasData.valid = false;
    return;
  }

  if (!checkChecksum(gasFrame)) {
    gasData.valid = false;
    return;
  }

  gasData.o2  = ((gasFrame[2] << 8) | gasFrame[3]) / 10.0;
  gasData.co  =  (gasFrame[4] << 8) | gasFrame[5];
  gasData.h2s = ((gasFrame[6] << 8) | gasFrame[7]) / 10.0;
  gasData.ch4 = ((gasFrame[8] << 8) | gasFrame[9]) / 10.0;
  gasData.valid = true;
}

void sendPacketToESP32() {
  Serial2.print("DATA,");
  Serial2.print(millis());
  Serial2.print(",");
  Serial2.print(scd30Ready ? 1 : 0);
  Serial2.print(",");
  Serial2.print(scdData.valid ? 1 : 0);
  Serial2.print(",");
  Serial2.print(scdData.temperature, 1);
  Serial2.print(",");
  Serial2.print(scdData.humidity, 1);
  Serial2.print(",");
  Serial2.print(scdData.co2, 0);
  Serial2.print(",");
  Serial2.print(gasData.valid ? 1 : 0);
  Serial2.print(",");
  Serial2.print(gasData.o2, 1);
  Serial2.print(",");
  Serial2.print(gasData.co);
  Serial2.print(",");
  Serial2.print(gasData.h2s, 1);
  Serial2.print(",");
  Serial2.println(gasData.ch4, 1);
}

void printSerialReport() {
  Serial.println("===== SENSOR DATA =====");

  if (scd30Ready && scdData.valid) {
    Serial.print("Temp: ");
    Serial.print(scdData.temperature, 1);
    Serial.println(" C");

    Serial.print("Humidity: ");
    Serial.print(scdData.humidity, 1);
    Serial.println(" %");

    Serial.print("CO2: ");
    Serial.print(scdData.co2, 0);
    Serial.println(" ppm");
  } else {
    Serial.println("SCD30: not ready");
  }

  if (gasData.valid) {
    Serial.print("O2: ");
    Serial.print(gasData.o2, 1);
    Serial.println(" %");

    Serial.print("CO: ");
    Serial.print(gasData.co);
    Serial.println(" ppm");

    Serial.print("H2S: ");
    Serial.print(gasData.h2s, 1);
    Serial.println(" ppm");

    Serial.print("CH4: ");
    Serial.print(gasData.ch4, 1);
    Serial.println(" %LEL");
  } else {
    Serial.println("Gas sensor: no data");
  }

  Serial.println("========================\n");
}

void setup() {
  Serial.begin(115200);
  Serial1.begin(9600);      // gas sensor UART
  Serial2.begin(115200);    // link to ESP32
  Wire.begin();

  scd30Ready = scd30.begin();
  if (scd30Ready) {
    scd30.setMeasurementInterval(2);   // fastest valid SCD30 setting
  }
}

void loop() {
  updateSCD30();
  updateGasSensor();

  unsigned long now = millis();
  if (now - lastSendMs >= sendIntervalMs) {
    lastSendMs = now;
    printSerialReport();
    sendPacketToESP32();
  }
}