#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>

#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif

#ifndef ESP32_TEST_LED_PIN
#define ESP32_TEST_LED_PIN LED_BUILTIN
#endif

namespace {
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr char READY_MESSAGE[] = "READY:esp32_test_firmware";
constexpr char RESULT_PREFIX[] = "TEST_RESULT:";
constexpr char SUMMARY_PREFIX[] = "TEST_SUMMARY:";
constexpr char NVS_NAMESPACE[] = "esp32_test";
constexpr char NVS_KEY[] = "validation";
constexpr uint32_t NVS_TEST_VALUE = 0xA55A39C6;
constexpr uint8_t LED_BLINK_COUNT = 5;

String commandBuffer;

String escapeJson(const String &value) {
  String escaped;
  escaped.reserve(value.length() + 8);
  for (size_t index = 0; index < value.length(); ++index) {
    char character = value[index];
    if (character == '"' || character == '\\') {
      escaped += '\\';
      escaped += character;
    } else if (character >= 0x20) {
      escaped += character;
    }
  }
  return escaped;
}

void emitResult(const char *name, bool passed, const String &detail,
                const String &dataJson = "{}") {
  Serial.print(RESULT_PREFIX);
  Serial.print("{\"name\":\"");
  Serial.print(name);
  Serial.print("\",\"status\":\"");
  Serial.print(passed ? "PASS" : "FAIL");
  Serial.print("\",\"detail\":\"");
  Serial.print(escapeJson(detail));
  Serial.print("\",\"data\":");
  Serial.print(dataJson);
  Serial.println("}");
}

void recordResult(const char *name, bool passed, const String &detail,
                 uint8_t &passedCount, uint8_t &failedCount,
                 const String &dataJson = "{}") {
  emitResult(name, passed, detail, dataJson);
  passed ? ++passedCount : ++failedCount;
}

String readMacAddress() {
  uint64_t mac = ESP.getEfuseMac();
  char address[18];
  snprintf(address, sizeof(address), "%02X:%02X:%02X:%02X:%02X:%02X",
           static_cast<uint8_t>(mac >> 40), static_cast<uint8_t>(mac >> 32),
           static_cast<uint8_t>(mac >> 24), static_cast<uint8_t>(mac >> 16),
           static_cast<uint8_t>(mac >> 8), static_cast<uint8_t>(mac));
  return String(address);
}

String boardInformationJson(uint32_t freeHeap, uint32_t minimumFreeHeap) {
  String data;
  data.reserve(240);
  data = "{\"chip_model\":\"";
  data += escapeJson(ESP.getChipModel());
  data += "\",\"chip_revision\":";
  data += String(ESP.getChipRevision());
  data += ",\"sdk_version\":\"";
  data += escapeJson(ESP.getSdkVersion());
  data += "\",\"flash_size_bytes\":";
  data += String(ESP.getFlashChipSize());
  data += ",\"cpu_frequency_mhz\":";
  data += String(ESP.getCpuFreqMHz());
  data += ",\"mac_address\":\"";
  data += readMacAddress();
  data += "\",\"free_heap_bytes\":";
  data += String(freeHeap);
  data += ",\"minimum_free_heap_bytes\":";
  data += String(minimumFreeHeap);
  data += "}";
  return data;
}

void runTests() {
  uint8_t passed = 0;
  uint8_t failed = 0;

  bool serialTest = static_cast<bool>(Serial);
  recordResult("serial", serialTest,
               serialTest ? "Serial is available" : "Serial is unavailable",
               passed, failed);

  uint32_t freeHeap = ESP.getFreeHeap();
  uint32_t minimumFreeHeap = ESP.getMinFreeHeap();
  bool heapTest = freeHeap > 0;
  String heapDetail = String(freeHeap) + " bytes free; minimum observed " +
                      String(minimumFreeHeap) + " bytes";
  String heapData = "{\"free_heap_bytes\":" + String(freeHeap) +
                    ",\"minimum_free_heap_bytes\":" + String(minimumFreeHeap) + "}";
  recordResult("free_heap", heapTest, heapDetail, passed, failed, heapData);

  String chipModel = ESP.getChipModel();
  bool chipTest = chipModel.length() > 0;
  recordResult("chip_info", chipTest,
               chipTest ? chipModel : "Chip model is unavailable", passed, failed);

  bool boardTest = chipTest && ESP.getFlashChipSize() > 0 &&
                   ESP.getCpuFreqMHz() > 0 && ESP.getSdkVersion() != nullptr;
  recordResult("board_info", boardTest,
               boardTest ? "Board information collected" : "Board information is incomplete",
               passed, failed, boardInformationJson(freeHeap, minimumFreeHeap));

  bool wifiModeReady = WiFi.mode(WIFI_STA);
  int networkCount = wifiModeReady ? WiFi.scanNetworks(false, true) : WIFI_SCAN_FAILED;
  bool wifiTest = networkCount > 0;
  String wifiDetail = networkCount >= 0
                          ? String(networkCount) + " access point(s) detected"
                          : "Wi-Fi scan failed or no access points were detected";
  String wifiData = "{\"network_count\":" + String(networkCount < 0 ? 0 : networkCount) +
                    ",\"scan_completed\":" +
                    String(networkCount >= 0 ? "true" : "false") + "}";
  recordResult("wifi_scan", wifiTest, wifiDetail, passed, failed, wifiData);
  WiFi.scanDelete();
  WiFi.mode(WIFI_OFF);

  Preferences preferences;
  bool nvsStarted = preferences.begin(NVS_NAMESPACE, false);
  size_t bytesWritten = nvsStarted ? preferences.putUInt(NVS_KEY, NVS_TEST_VALUE) : 0;
  uint32_t valueRead = nvsStarted ? preferences.getUInt(NVS_KEY, 0) : 0;
  bool nvsTest = nvsStarted && bytesWritten == sizeof(NVS_TEST_VALUE) &&
                 valueRead == NVS_TEST_VALUE;
  if (nvsStarted) {
    if (preferences.isKey(NVS_KEY)) {
      preferences.remove(NVS_KEY);
    }
    preferences.end();
  }
  recordResult("nvs", nvsTest,
               nvsTest ? "NVS write/read integrity verified"
                       : "NVS write/read integrity check failed",
               passed, failed,
               "{\"bytes_written\":" + String(bytesWritten) +
                   ",\"integrity_verified\":" + String(nvsTest ? "true" : "false") + "}");

  pinMode(ESP32_TEST_LED_PIN, OUTPUT);
  for (uint8_t blink = 0; blink < LED_BLINK_COUNT; ++blink) {
    digitalWrite(ESP32_TEST_LED_PIN, HIGH);
    delay(100);
    digitalWrite(ESP32_TEST_LED_PIN, LOW);
    delay(100);
  }
  recordResult("gpio", true, "Onboard LED output toggled five times", passed, failed,
               "{\"pin\":" + String(ESP32_TEST_LED_PIN) +
                   ",\"blink_count\":" + String(LED_BLINK_COUNT) + "}");

  Serial.print(SUMMARY_PREFIX);
  Serial.print("{\"total\":");
  Serial.print(passed + failed);
  Serial.print(",\"passed\":");
  Serial.print(passed);
  Serial.print(",\"failed\":");
  Serial.print(failed);
  Serial.println("}");
}

void handleCommand(const String &command) {
  if (command == "PING") {
    Serial.println("PONG");
  } else if (command == "RUN_TESTS") {
    runTests();
  } else if (command == "HELP") {
    Serial.println("COMMANDS:PING,RUN_TESTS,HELP");
  } else if (command.length() > 0) {
    Serial.println("ERROR:UNKNOWN_COMMAND");
  }
}
}  // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);
  const uint32_t serialStart = millis();
  while (!Serial && millis() - serialStart < 3000) {
    delay(10);
  }

  Serial.println();
  Serial.print("BOOT:firmware=esp32_test_firmware,chip=");
  Serial.print(ESP.getChipModel());
  Serial.print(",revision=");
  Serial.print(ESP.getChipRevision());
  Serial.print(",flash_bytes=");
  Serial.println(ESP.getFlashChipSize());
  Serial.println(READY_MESSAGE);
}

void loop() {
  while (Serial.available() > 0) {
    char character = static_cast<char>(Serial.read());
    if (character == '\n') {
      commandBuffer.trim();
      handleCommand(commandBuffer);
      commandBuffer = "";
    } else if (character != '\r') {
      if (commandBuffer.length() < 64) {
        commandBuffer += character;
      } else {
        commandBuffer = "";
        Serial.println("ERROR:COMMAND_TOO_LONG");
      }
    }
  }
}
