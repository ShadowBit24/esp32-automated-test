# Healthy ESP32 Validation — Sanitized Report Excerpt

Source: `reports/esp32_test_report_20261101_013038_063011.md`, generated
2026-11-01T05:30:38Z. Device identifiers and detailed raw output are omitted.

- **Overall status:** PASS
- **Board:** ESP32-D0WD-V3, revision 3; 4 MB flash
- **Firmware tests:** 7/7 PASS
  - Serial, heap, chip information, board information, Wi-Fi scan, NVS, GPIO
- **Wi-Fi:** 10 access points detected
- **NVS:** write/read integrity verified
- **GPIO:** five software output toggles
- **Flash diagnostics:** chip ID PASS; flash ID PASS; flash status PASS
- **Boot classification:** `POWERON_RESET` (expected cold boot)
- **Health score:** 100/100 — `HEALTHY`

GPIO PASS confirms software toggling only; it does not prove visible LED
illumination or electrical continuity.
