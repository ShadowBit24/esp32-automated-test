# ESP32 Automated Validation Framework — Project Audit

## Scope and inventory

The complete repository was inspected before implementation changes.

| Path | Existing responsibility | Audit notes |
|---|---|---|
| `firmware/esp32_test_firmware.ino` | Serial command protocol and device self-tests | Implements `PING`, `HELP`, `RUN_TESTS`, and three PASS/FAIL records (`serial`, `free_heap`, `chip_info`). No structured board inventory, Wi-Fi, NVS, or GPIO tests. |
| `host/test_runner.py` | Serial test orchestration and JSON protocol parsing | Requires `--port`; no port discovery, hardware flash diagnostics, or persistent raw session log. Errors preserve received lines in reports but do not run the boot analyzer on normal logs beyond a minimal classification. |
| `host/bootlog_analyzer.py` | Boot log classification | Recognizes invalid-image text, a subset of watchdog indications, and panic text. Does not recognize requested reset reasons such as `RTCWDT_RTC_RESET`, `POWERON_RESET`, `SW_RESET`, `TG0WDT_SYS_RESET`, `TG1WDT_SYS_RESET`, or `BROWNOUT_RESET`; results have no severity, causes, or actions. |
| `host/flash_validator.py` | Offline ESP application image structure/checksum validation | Validates image magic, segment boundaries, checksum, and an appended digest. It does not communicate with a board. |
| `host/report_generator.py` | Timestamped JSON and Markdown run reports | Includes basic test rows and a short boot classification only; no board inventory, flash diagnostics, actionable boot details, raw boot log, health score, classification, or final verdict. |
| `sample_logs/invalid_header.log` | Invalid-image example | Contains `invalid header: 0xffffffff` and an RTC watchdog reset, but the analyzer does not identify that reset reason. |
| `sample_logs/watchdog_reset.log` | Watchdog example | Includes a TG1 watchdog reset and task watchdog message; only the generic task watchdog text is recognized. |
| `sample_logs/normal_boot.log` | Successful firmware example | Demonstrates the existing protocol and three tests. |
| `reports/.gitkeep` | Keeps the report directory | No generated reports or raw-session log were present at audit time. |
| `README.md` | Setup and usage documentation | Accurately describes the original three-test serial harness and offline validator, but not the requested automated-validation capabilities. |

No dependency manifest or automated test suite was present at audit time.

## README claims versus implementation

| README statement | Implementation status |
|---|---|
| Firmware accepts `PING`, `RUN_TESTS`, and `HELP` at 115200 baud | Implemented |
| `RUN_TESTS` emits JSON result records and a summary | Implemented for the three original tests |
| Device tests cover serial, non-zero free heap, and chip model | Implemented |
| Host test runner connects to a specified serial port | Implemented; `--port` was mandatory |
| Runner checks summary/result count consistency and writes JSON/Markdown reports | Implemented |
| Boot analyzer classifies common failures | Partially implemented; only a small pattern set and generic labels |
| Flash validator checks image structure, checksum, and optional SHA-256 | Implemented offline; no hardware flash diagnostics |
| Reports are written under `reports/` | Implemented for completed/failed runner invocations |

The README did not claim auto-detection, Wi-Fi/NVS/GPIO, board health scoring,
structured root-cause advice, raw session capture, or esptool hardware checks.
Those are project-objective additions rather than existing behavior.

## Gap analysis

1. **Hardware discovery and reproducibility:** No USB serial enumeration; an operator must know and pass the port. Logs are parsed into lines but the raw session is not saved.
2. **Board validation coverage:** No structured board details, Wi-Fi scan, NVS write/read integrity test, or onboard-LED GPIO exercise.
3. **Failure diagnosis:** Reset reasons and flash-read errors are not classified consistently. Findings lack severity, likely causes, and recommended next actions.
4. **Flash health:** The existing validator checks a file only. It does not run chip identification, flash identification, or flash-status commands against attached hardware.
5. **At-a-glance verdict:** Reports have no explicit health score, health class, board/flash sections, or consolidated final verdict.
6. **Dependencies and verification:** No declared host dependencies or maintained automated tests; hardware and esptool availability are not represented in reports.
7. **Hardware variability:** Built-in LED pins, access-point availability, USB bridge identifiers, esptool CLI versions, and board auto-reset behavior vary across setups and must be documented or handled explicitly.

## Improvements ranked by impact

| Rank | Improvement | Impact |
|---:|---|---|
| 1 | Expand boot diagnostics for reset reasons, invalid headers, flash read errors, and panic text; attach severity, likely causes, and actions | High: helps distinguish power, watchdog, image/partition, and runtime failures from real captured logs |
| 2 | Capture and persist raw serial output for successful and failed sessions | High: preserves evidence for diagnosis and reproducibility |
| 3 | Add structured board information plus Wi-Fi, NVS, and GPIO tests | High: validates the requested hardware paths and exposes useful inventory |
| 4 | Add serial-port auto-detection with explicit override and ambiguity handling | High: reduces setup friction without silently selecting an arbitrary board |
| 5 | Run esptool chip ID, flash ID, and flash status checks and parse common connection/flash failures | High: adds direct hardware-side flash diagnostics alongside the existing file validator |
| 6 | Produce a transparent 0–100 health score, classification, and verdict | Medium-high: makes a run actionable while exposing component-level evidence |
| 7 | Expand report output and documentation; declare host requirements and add repeatable offline tests | Medium-high: makes output complete and validates behavior without connected hardware |

## Implementation constraints and assumptions

- Keep the existing serial command names, result prefix, summary prefix, and
  original test names so older host consumers remain compatible; additional
  structured fields and tests are additive.
- Treat port discovery as a safe candidate selection, not proof of board
  identity. Multiple candidates require an explicit `--port`.
- Treat Wi-Fi scan success as at least one visible access point, as requested;
  RF environment therefore affects the test result.
- Exercise the configured onboard LED pin in software; without external
  electrical feedback, a blink cannot prove the LED or GPIO wiring physically
  works.
- Report esptool unavailable/unsupported operations explicitly rather than
  silently claiming flash health.
- A boot-log diagnosis identifies likely causes, not a definitive hardware
  root cause. Health scoring is an operational heuristic and reports its
  component scores.

## Post-implementation verification

- Added the requested host and firmware features while retaining the existing
  serial commands, record prefixes, original test names, `write_report` return
  shape, and offline image validator.
- Updated the README to match the expanded behavior and document environmental
  limitations and score weights.
- Added `requirements.txt` and 12 offline regression tests.
- Python syntax checks and imports passed; all 12 offline tests passed.
- Sample logs classify as normal boot, invalid image (including all three
  requested non-`0xffffffff` header values), and TG1 watchdog reset.
- Synthetic tests cover every requested reset reason, flash error text, port
  ambiguity/override, serial JSON protocol, raw log persistence, health-score
  shape, report sections, and valid/invalid ESP image checks.
- Installed dependencies from the manifest and confirmed the selected esptool
  CLI exposes `chip-id`, `flash-id`, and `read-flash-status`.
- Follow-up hardware session detected the ESP32-D0WD-V3 on COM6 with a
  CP210x bridge; esptool reported a 4 MB BoyaMicro flash (manufacturer 0x68,
  device 0x4016) and status register 0x0200.
- The initial raw boot capture showed repeated `invalid header: 0x3ffea272`
  and `RTCWDT_RTC_RESET`; hardware chip/flash/status commands all succeeded.
- Follow-up work added the PlatformIO DOUT/40 MHz board profile and built the
  test firmware. Build and upload outcomes are recorded in the hardware
  follow-up session.
- Hardware inspection found flash encryption enabled (`FLASH_CRYPT_CNT=1`) on
  the connected ESP32-D0WD-V3. Plaintext uploads were therefore not a valid
  deployment path. An IDF 6.1 encryption-aware bootloader was built with
  `CONFIG_SECURE_FLASH_REQUIRE_ALREADY_ENABLED`; no eFuses were changed and no
  full-flash erase was performed.
- The bootloader required the existing partition table to be written in the
  encrypted format. The original table layout was preserved, and the bootloader,
  partition table, OTA app0 selection record, and app0 image were written with
  esptool `--encrypt`. This removed the bootloader's invalid OTA-data fallback.
- The first hardware run exposed an incomplete firmware summary JSON record;
  its closing brace was added. The PlatformIO source filter now excludes the
  nested IDF support project, and the helper project's build output is outside
  the Arduino source tree.
- Final connected-board verification passed all seven firmware tests (including
  a Wi-Fi scan detecting 10 access points) and all three esptool diagnostics.
  The report classified the board as `HEALTHY` at 100/100. The 13 offline host
  regression tests and both PlatformIO builds passed.
- Remaining physical limitation: the GPIO test confirms software toggling but
  cannot verify LED illumination or pin continuity without external feedback.
