#include <Arduino.h>
#include <M5Unified.h>
#include <ESPNowCam.h>
#include <esp_camera.h>

#define STREAM_SERIAL
// #define VIEW_LCD

ESPNowCam nowCam;

// frame buffer
uint8_t *fb; 
// display globals
int32_t dw, dh;

// 前回の送信時刻
unsigned long previousMillis = 0;
// シリアル通信の送信間隔（ミリ秒）
const long interval = 200;

void onDataReady(uint32_t length) {

  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;

#ifdef STREAM_SERIAL
    Serial.write(fb, length);
    Serial.write((uint8_t)0xFF);
    Serial.write((uint8_t)0xD9);
    Serial.flush(); // バッファをクリア
    Serial.printf("Sent %d bytes via serial.\n", length + 2); // デバッグメッセージを修正
#endif

#ifdef VIEW_LCD
  // ディスプレイとシリアル通信の同時処理はCore2では厳しいためシリアル通信を使用する場合はコメントアウト
  M5.Display.drawJpg(fb, length , 0, 0, dw, dh);
#endif
  }

}

void setup() {
  Serial.begin(460800);
  auto cfg = M5.config();
  M5.begin(cfg);

  M5.Display.setBrightness(96);
  M5.Display.setTextSize(2);
  dw=M5.Display.width();
  dh=M5.Display.height();

  M5.Display.drawCenterString("ESPNowCam Reciever", dw / 2, dh / 2 - 75);
  M5.Display.drawCenterString("==================", dw / 2, dh / 2 - 60);
  M5.Display.setTextSize(2);

  //------------------------------------
  // PSRAM初期設定
  if(psramFound()){
    size_t psram_size = esp_spiram_get_size() / 1048576;
    Serial.printf("PSRAM size: %dMb\r\n", psram_size);
  }
  // BE CAREFUL WITH IT, IF JPG LEVEL CHANGES, INCREASE IT
  fb = static_cast<uint8_t*>(ps_malloc(15000 * sizeof(uint8_t)));

  M5.Display.drawCenterString("PSRAM Init Success", dw / 2, dh / 2 - 30);
  Serial.println("ESPNow Init Success");
  delay(500);

  //------------------------------------
  // ESPNowCam初期設定
  nowCam.setRecvBuffer(fb);
  nowCam.setRecvCallback(onDataReady);
  if (nowCam.init()) {
    M5.Display.drawCenterString("ESPNow Init Success", dw / 2, dh / 2);
    Serial.println("ESPNow Init Success");
  } 
  M5.Display.drawCenterString("Setup All Success", dw / 2, dh / 2 + 30);
  M5.Display.drawCenterString("Check the serial monitor", dw / 2, dh / 2 + 60);
  Serial.println("ESPNow Init Success");
  delay(500);

}

void loop() {
}
