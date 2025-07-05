#include <Arduino.h>
#include <ESPNowCam.h>
#include <SPIFFS.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
ESPNowCam radio;

// Constants
#define WIFI_CHANNEL 1
#define MAX_IMAGE_SIZE 65536
#define HEADER_SIZE 5  // Taille de l'en-tête ESPNowCam
const char* WIFI_SSID = "Kapmid";
const char* WIFI_PASSWORD = "12341234";

// Structure pour les commandes (compatible avec le code d'origine)
struct CommandData {
  uint8_t command;  // 1:shoot, 2:zoomIn, 3:zoomOut, 4:pan, 5:tilt
  int16_t value;    // Valeur pour pan/tilt
};

// Global variables
WebServer server(80);
uint8_t* imageBuffer = nullptr;
size_t imageSize = 0;
bool newImageAvailable = false;
SemaphoreHandle_t imageMutex = nullptr;
unsigned long lastPacketTime = 0;
unsigned long packetCount = 0;

// Buffer temporaire pour assembler l'image
uint8_t* tempBuffer = nullptr;
size_t tempSize = 0;
bool isCollectingImage = false;
// Dans l'ESP récepteur, pour envoyer à tous
// uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
uint8_t broadcastAddress[] = {0xF0, 0x9E, 0x9E, 0x32, 0x5B, 0x24};

// Fonction pour envoyer une commande via ESP-NOW
void sendCommand(uint8_t cmd) {
  Serial.println("================");
  Serial.println("SENDING COMMAND");
  CommandData data = {cmd};

  radio.sendData((uint8_t*)&data, sizeof(CommandData));
  Serial.println("================");
}

void handleCommand() {
  String cmd = server.arg("cmd");

  Serial.println(cmd);
  if (cmd == "left") {
    sendCommand(4);  // Pan left
  } else if (cmd == "right") {
    sendCommand(3);  // Pan right
  } else if (cmd == "shoot") {
    sendCommand(1);  // Take photo
  }

  server.send(200, "text/plain", "OK");
  Serial.println(cmd);
  delay(1000);
}

void initSPIFFS() {
  if (!SPIFFS.begin(true)) {
    Serial.println("SPIFFS Mount Failed");
    return;
  }

  // Liste les fichiers dans SPIFFS
  File root = SPIFFS.open("/");
  File file = root.openNextFile();
  while (file) {
    Serial.print("File: ");
    Serial.println(file.name());
    file = root.openNextFile();
  }
}

void handleRoot() {
  File file = SPIFFS.open("/index.html", "r");
  if (!file) {
    server.send(500, "text/plain", "Internal Server Error");
    return;
  }
  server.streamFile(file, "text/html");
  file.close();
}

void dumpPacketInfo(const uint8_t* data, int len) {
  Serial.printf("Packet Length: %d bytes\n", len);
  Serial.print("Header: ");
  for (int i = 0; i < HEADER_SIZE; i++) {
    Serial.printf("%02X ", data[i]);
  }
  Serial.print(" | Data: ");
  for (int i = HEADER_SIZE; i < min(HEADER_SIZE + 8, len); i++) {
    Serial.printf("%02X ", data[i]);
  }
  Serial.println();
}

// ESP-NOW receive callback
void onDataReceived(const uint8_t* mac, const uint8_t* data, int len) {
  packetCount++;
  lastPacketTime = millis();

  if (len <= HEADER_SIZE || len > MAX_IMAGE_SIZE) return;

  // Vérifier les données après l'en-tête
  const uint8_t* imageData = data + HEADER_SIZE;
  int imageDataLen = len - HEADER_SIZE;

  // Vérifier si c'est le début d'une image JPEG
  if (imageDataLen > 1 && imageData[0] == 0xFF && imageData[1] == 0xD8) {
    Serial.println("New JPEG frame starting");
    isCollectingImage = true;
    tempSize = 0;

    if (!tempBuffer) {
      tempBuffer = (uint8_t*)malloc(MAX_IMAGE_SIZE);
      if (!tempBuffer) {
        Serial.println("Failed to allocate temp buffer!");
        return;
      }
    }
  }

  // Si nous sommes en train de collecter une image
  if (isCollectingImage && tempBuffer) {
    if (tempSize + imageDataLen <= MAX_IMAGE_SIZE) {
      memcpy(tempBuffer + tempSize, imageData, imageDataLen);
      tempSize += imageDataLen;
      //            Serial.printf("Accumulated %d bytes\n", tempSize);

      // Chercher le marqueur de fin JPEG dans ce paquet
      for (int i = 0; i < imageDataLen - 1; i++) {
        if (imageData[i] == 0xFF && imageData[i + 1] == 0xD9) {
          //                    Serial.println("JPEG End Marker found!");

          if (xSemaphoreTake(imageMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
            if (imageBuffer) free(imageBuffer);
            imageBuffer = (uint8_t*)malloc(tempSize);

            if (imageBuffer) {
              memcpy(imageBuffer, tempBuffer, tempSize);
              imageSize = tempSize;
              newImageAvailable = true;
              //                            Serial.printf("Complete image stored: %d bytes\n",
              //                            imageSize);
            }
            xSemaphoreGive(imageMutex);
          }

          isCollectingImage = false;
          break;
        }
      }
    } else {
      Serial.println("Buffer overflow, resetting collection");
      isCollectingImage = false;
    }
  }
}

void handleStream() {
  if (!xSemaphoreTake(imageMutex, pdMS_TO_TICKS(100))) {
    server.send(503, "text/plain", "Server busy");
    return;
  }

  if (!imageBuffer || imageSize == 0) {
    xSemaphoreGive(imageMutex);
    server.send(404, "text/plain", "No image available");
    return;
  }

  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  server.sendHeader("Pragma", "no-cache");
  server.sendHeader("Expires", "0");
  server.sendHeader("Content-Type", "image/jpeg");
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send_P(200, "image/jpeg", (char*)imageBuffer, imageSize);

  xSemaphoreGive(imageMutex);
}

void setup() {
  Serial.begin(115200);

  // Initialize SPIFFS
  initSPIFFS();
  // Initialize mutex
  imageMutex = xSemaphoreCreateMutex();
  if (!imageMutex) return;

  // Initialize WiFi in AP+STA mode

  WiFi.mode(WIFI_AP_STA);
  IPAddress AP_IP(192, 168, 4, 8);
  WiFi.softAPConfig(AP_IP, AP_IP, IPAddress(255, 255, 255, 0));
  // Initialize ESP-NOW

  // const uint8_t macRecv[6] = {0xDC,0x54,0x75,0xD1,0x65,0xBC};
  radio.setTarget(broadcastAddress);
  radio.init();
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  esp_now_register_recv_cb(onDataReceived);
  // Configure WiFi AP
  WiFi.softAP(WIFI_SSID, WIFI_PASSWORD, WIFI_CHANNEL, 0);

  // Configure web server
  server.on("/", handleRoot);
  server.on("/stream", handleStream);
  server.on("/command", handleCommand);
  server.begin();

  Serial.print("Camera stream available at: http://192.168.4.8");
}

void loop() {
  server.handleClient();
  // Print statistics every second
  static unsigned long lastStats = 0;
  if (millis() - lastStats >= 1000) {
    Serial.printf("Packets/sec: %lu ", packetCount);
    if (newImageAvailable) {
      Serial.printf("(Last image: %d bytes)", imageSize);
    }
    Serial.println();
    packetCount = 0;
    lastStats = millis();
  }
  delay(1);
}