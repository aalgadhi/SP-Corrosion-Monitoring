#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <SPI.h>
#include <WiFi.h>
#include <WiFiUdp.h>

#define TFT_CS   5
#define TFT_DC   2
#define TFT_RST  4
#define TFT_MOSI 23
#define TFT_SCLK 18
#define TFT_MISO 19

#define MEGA_RX 16
#define MEGA_TX 17

const char *WIFI_SSID = "TP-Link_2D9C";
const char *WIFI_PASSWORD = "39650184";
const IPAddress PC_IP(192, 168, 0, 154);
const uint16_t PC_PORT = 5005;

Adafruit_ILI9341 tft(TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_RST, TFT_MISO);
HardwareSerial megaLink(2);
WiFiUDP udp;

struct DisplayData {
  bool scd30Ready;
  bool scd30Valid;
  float temperature;
  float humidity;
  float co2;
  bool gasValid;
  float o2;
  int co;
  float h2s;
  float ch4;
  bool packetSeen;
};

DisplayData data = {false, false, 0, 0, 0, false, 0, 0, 0, 0, false};

char rxLine[128];
size_t rxPos = 0;

unsigned long lastWifiAttemptMs = 0;
unsigned long lastFooterRefreshMs = 0;

const uint16_t COLOR_HEADER = 0x0410;
const uint16_t COLOR_CO2 = 0xFD20;

// portrait layout tuned to avoid overlap
const int LABEL_X = 6;
const int VALUE_X = 118;
const int ROW_H   = 26;

const int ROW_TEMP = 40;
const int ROW_HUM  = 66;
const int ROW_CO2  = 92;
const int ROW_O2   = 130;
const int ROW_CO   = 156;
const int ROW_H2S  = 182;
const int ROW_CH4  = 208;

void wifiMaintain() {
  if (WiFi.status() == WL_CONNECTED) return;

  unsigned long now = millis();
  if (now - lastWifiAttemptMs < 5000) return;

  lastWifiAttemptMs = now;
  WiFi.disconnect(false, false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void sendUdpPacket(const char *packet) {
  if (WiFi.status() != WL_CONNECTED) return;
  udp.beginPacket(PC_IP, PC_PORT);
  udp.print(packet);
  udp.endPacket();
}

bool parsePacketIntoData(const char *line, DisplayData &out) {
  unsigned long senderMs = 0;
  int scdReadyInt = 0, scdValidInt = 0, gasValidInt = 0;
  float temperature = 0, humidity = 0, co2 = 0, o2 = 0, h2s = 0, ch4 = 0;
  int co = 0;

  int n = sscanf(
    line,
    "DATA,%lu,%d,%d,%f,%f,%f,%d,%f,%d,%f,%f",
    &senderMs,
    &scdReadyInt,
    &scdValidInt,
    &temperature,
    &humidity,
    &co2,
    &gasValidInt,
    &o2,
    &co,
    &h2s,
    &ch4
  );

  if (n != 11) return false;

  out.scd30Ready = (scdReadyInt != 0);
  out.scd30Valid = (scdValidInt != 0);
  out.temperature = temperature;
  out.humidity = humidity;
  out.co2 = co2;
  out.gasValid = (gasValidInt != 0);
  out.o2 = o2;
  out.co = co;
  out.h2s = h2s;
  out.ch4 = ch4;
  out.packetSeen = true;
  return true;
}

void drawStaticLayout() {
  tft.fillScreen(ILI9341_BLACK);

  tft.setTextSize(2);
  tft.setTextColor(ILI9341_CYAN, ILI9341_BLACK);
  tft.setCursor(10, 8);
  tft.print("Sensors");
  tft.drawFastHLine(0, 28, tft.width(), COLOR_HEADER);

  tft.setTextSize(2);
  tft.setTextColor(ILI9341_WHITE, ILI9341_BLACK);

  tft.setCursor(LABEL_X, ROW_TEMP); tft.print("Temp");
  tft.setCursor(LABEL_X, ROW_HUM ); tft.print("Hum");
  tft.setCursor(LABEL_X, ROW_CO2 ); tft.print("CO2");
  tft.setCursor(LABEL_X, ROW_O2  ); tft.print("O2");
  tft.setCursor(LABEL_X, ROW_CO  ); tft.print("CO");
  tft.setCursor(LABEL_X, ROW_H2S ); tft.print("H2S");
  tft.setCursor(LABEL_X, ROW_CH4 ); tft.print("CH4");

  tft.drawFastVLine(VALUE_X - 8, 34, 192, COLOR_HEADER);
  tft.drawFastHLine(0, 232, tft.width(), COLOR_HEADER);
}

void clearValueRow(int y) {
  tft.fillRect(VALUE_X, y, 120, ROW_H, ILI9341_BLACK);
}

void drawValue(int y, const char *text, uint16_t color) {
  clearValueRow(y);
  tft.setTextSize(2);
  tft.setCursor(VALUE_X, y);
  tft.setTextColor(color, ILI9341_BLACK);
  tft.print(text);
}

void drawFooter() {
  tft.fillRect(0, 236, tft.width(), 84, ILI9341_BLACK);

  tft.setTextSize(1);
  tft.setTextColor(ILI9341_WHITE, ILI9341_BLACK);

  tft.setCursor(6, 240);
  if (WiFi.status() == WL_CONNECTED) {
    tft.print("WiFi OK");
  } else {
    tft.print("WiFi reconnecting");
  }

  tft.setCursor(6, 252);
  if (WiFi.status() == WL_CONNECTED) {
    tft.print(WiFi.localIP());
  } else {
    tft.print("No IP");
  }
}

void updateDisplayFast() {
  char buf[24];

  if (!data.packetSeen) {
    drawValue(ROW_TEMP, "Waiting", ILI9341_WHITE);
    drawValue(ROW_HUM,  "--", ILI9341_WHITE);
    drawValue(ROW_CO2,  "--", ILI9341_WHITE);
    drawValue(ROW_O2,   "--", ILI9341_WHITE);
    drawValue(ROW_CO,   "--", ILI9341_WHITE);
    drawValue(ROW_H2S,  "--", ILI9341_WHITE);
    drawValue(ROW_CH4,  "--", ILI9341_WHITE);
    drawFooter();
    return;
  }

  if (!data.scd30Ready) {
    drawValue(ROW_TEMP, "No SCD30", ILI9341_RED);
    drawValue(ROW_HUM,  "--", ILI9341_WHITE);
    drawValue(ROW_CO2,  "--", ILI9341_WHITE);
  } else if (!data.scd30Valid) {
    drawValue(ROW_TEMP, "Reading", ILI9341_WHITE);
    drawValue(ROW_HUM,  "--", ILI9341_WHITE);
    drawValue(ROW_CO2,  "--", ILI9341_WHITE);
  } else {
    snprintf(buf, sizeof(buf), "%.1f C", data.temperature);
    drawValue(ROW_TEMP, buf, ILI9341_YELLOW);

    snprintf(buf, sizeof(buf), "%.1f %%", data.humidity);
    drawValue(ROW_HUM, buf, ILI9341_GREEN);

    snprintf(buf, sizeof(buf), "%.0f ppm", data.co2);
    drawValue(ROW_CO2, buf, COLOR_CO2);
  }

  if (!data.gasValid) {
    drawValue(ROW_O2,  "Reading", ILI9341_WHITE);
    drawValue(ROW_CO,  "--", ILI9341_WHITE);
    drawValue(ROW_H2S, "--", ILI9341_WHITE);
    drawValue(ROW_CH4, "--", ILI9341_WHITE);
  } else {
    snprintf(buf, sizeof(buf), "%.1f %%", data.o2);
    drawValue(ROW_O2, buf, ILI9341_CYAN);

    snprintf(buf, sizeof(buf), "%d ppm", data.co);
    drawValue(ROW_CO, buf, ILI9341_MAGENTA);

    snprintf(buf, sizeof(buf), "%.1f ppm", data.h2s);
    drawValue(ROW_H2S, buf, ILI9341_GREEN);

    snprintf(buf, sizeof(buf), "%.1f %%", data.ch4);
    drawValue(ROW_CH4, buf, ILI9341_BLUE);
  }

  drawFooter();
}

void setup() {
  Serial.begin(115200);
  megaLink.begin(115200, SERIAL_8N1, MEGA_RX, MEGA_TX);

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  tft.begin();
  tft.setRotation(0);   // portrait
  drawStaticLayout();
  updateDisplayFast();

  Serial.println("ESP32 display start");
}

void loop() {
  wifiMaintain();

  bool gotNewPacket = false;
  DisplayData newestData;

  while (megaLink.available()) {
    char c = (char)megaLink.read();

    if (c == '\n') {
      rxLine[rxPos] = '\0';

      if (strncmp(rxLine, "DATA,", 5) == 0) {
        sendUdpPacket(rxLine);

        DisplayData parsed;
        if (parsePacketIntoData(rxLine, parsed)) {
          newestData = parsed;
          gotNewPacket = true;
        }
      }

      rxPos = 0;
    } else if (c != '\r') {
      if (rxPos < sizeof(rxLine) - 1) {
        rxLine[rxPos++] = c;
      } else {
        rxPos = 0;
      }
    }
  }

  if (gotNewPacket) {
    data = newestData;
    updateDisplayFast();
  }

  if (millis() - lastFooterRefreshMs >= 1000) {
    lastFooterRefreshMs = millis();
    drawFooter();
  }
}
