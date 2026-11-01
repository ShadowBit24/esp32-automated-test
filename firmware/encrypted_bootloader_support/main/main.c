#include "esp_flash_encrypt.h"
#include "esp_log.h"
#include "esp_system.h"

void app_main(void) {
  if (!esp_flash_encryption_enabled()) {
    ESP_LOGE("secure_boot", "Flash encryption is not enabled; refusing to run.");
    abort();
  }
  ESP_LOGI("secure_boot", "Encrypted bootloader loaded the application.");
}
