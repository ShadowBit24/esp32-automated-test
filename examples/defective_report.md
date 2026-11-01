# Initial ESP32 Boot Failure — Sanitized Report Excerpt

Source: `reports/esp32_test_report_20261101_005740_403264.md`, generated
2026-11-01T04:57:40Z. Device identifiers and repeated raw log lines are omitted.

- **Overall status:** ERROR
- **Firmware tests:** none; firmware never reached `READY`
- **Boot classification:** `INVALID_IMAGE`
- **Observed boot output:** `invalid header: 0x3ffea272`;
  `RTCWDT_RTC_RESET`
- **Flash diagnostics:** chip ID PASS; flash ID PASS; flash status PASS
- **Health score:** 15/100 — `DEFECTIVE`

The passing flash diagnostics established communication with the ROM
bootloader and successful flash identification/status reads. They did not
establish that the application image was readable or bootable. Subsequent
investigation found flash encryption enabled and a mismatch between device
encryption state and flashed images; see
[`RECOVERY_ANALYSIS.md`](../RECOVERY_ANALYSIS.md) for the full evidence and
confidence limits.
