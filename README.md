# ESP32 Automated Validation Framework

## Badges

[![ESP32](https://img.shields.io/badge/target-ESP32-E7352C?logo=espressif&logoColor=white)](https://www.espressif.com/en/products/socs/esp32)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PlatformIO](https://img.shields.io/badge/build-PlatformIO-F5822A?logo=platformio&logoColor=white)](https://platformio.org/)
[![Arduino ESP32](https://img.shields.io/badge/framework-Arduino%20ESP32-00979D?logo=arduino&logoColor=white)](https://github.com/espressif/arduino-esp32)
[![esptool](https://img.shields.io/badge/diagnostics-esptool-333333)](https://github.com/espressif/esptool)
[![Active Project](https://img.shields.io/badge/project-active%20development-brightgreen)](ROADMAP.md)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **GitHub repository badges:** No Git remote or published repository was present when this README was reviewed. Stars, forks, issues, and last-commit badges are intentionally omitted rather than shown with fabricated repository coordinates. Add them when the project is published.

A practical firmware and host-side test framework for validating ESP32 boards,
capturing boot evidence, and diagnosing common startup and flash failures. An
Arduino-ESP32 sketch runs board tests; a Python CLI discovers the serial device,
collects results, analyzes boot output, runs esptool diagnostics, scores
hardware health, and writes JSON and Markdown reports.

## Overview

The project is designed to make board validation repeatable and useful during
firmware bring-up. It combines on-device checks with host diagnostics and
preserves the captured serial session for later investigation. The 0–100 health
score and root-cause suggestions are diagnostic aids, not a hardware
certification or substitute for electrical measurements.

The project has been exercised on an ESP32-D0WD-V3 development board with
4 MB BoyaMicro flash. Its current PlatformIO profile uses DOUT at 40 MHz and a
custom partition layout; verify those settings before using a different board.

## Key Features

- **Automatic ESP32 detection** using USB serial descriptions and vendor IDs,
  with an explicit `--port` override and safe handling of ambiguous devices.
- **Board information**: chip model and revision, SDK version, flash size, CPU
  frequency, MAC address, free heap, and minimum free heap.
- **Wi-Fi validation** in station mode; PASS requires a completed scan and at
  least one visible access point.
- **GPIO validation**: five software output toggles on `LED_BUILTIN` or the
  configurable fallback pin.
- **NVS validation**: write, read, and compare a value using Preferences.
- **Boot-log analysis** with severity, likely causes, recommended actions, and
  matching lines.
- **Flash diagnostics** using esptool chip-ID, flash-ID, and flash-status
  operations, with connection and flash failure output captured.
- **Health scoring** from 0 to 100 and `HEALTHY`, `SUSPECT`, or `DEFECTIVE`
  classification.
- **JSON report generation** for machine-readable run data.
- **Markdown report generation** for readable summaries and findings.
- **Raw serial log capture** at `reports/raw_serial_log.txt` (overwritten by
  the latest run in the selected report directory).
- **Offline firmware image validation** for ESP image structure, checksum, and
  appended SHA-256 when present.

## Real-World Investigation

The workspace includes a documented recovery of an ESP32 that initially
appeared to have a boot or hardware failure.

**Symptoms**

- Repeated `invalid header: 0x3ffea272` messages.
- `rst:0x10 (RTCWDT_RTC_RESET)` and no firmware `READY` announcement.
- The host could not run the firmware tests.

**Initial hypothesis:** possible hardware failure.

**Investigation findings**

- Chip-ID diagnostic: **PASS**.
- Flash-ID diagnostic: **PASS**.
- Flash-status diagnostic: **PASS**.
- An earlier eFuse inspection recorded flash encryption as enabled. Plaintext
  images are incompatible with that device state.
- Bootloader, partition table, OTA selection metadata, and application images
  were subsequently written using an encryption-aware workflow. The board
  then reached `READY` and completed the test suite.

**Most likely root cause:** flash-encryption configuration mismatch between
the encrypted device and the images being flashed. The passing ID/status
checks show that the ROM bootloader could communicate with and identify the
flash; they do not prove that the application image was readable or bootable.

**Outcome:** the recorded health score improved from **15/100 (`DEFECTIVE`)**
to **100/100 (`HEALTHY`)**. The report evidence supports this diagnosis, but
does not establish that every physical board failure can be resolved this way.
See [RECOVERY_ANALYSIS.md](RECOVERY_ANALYSIS.md) for the evidence, timeline,
commands, and confidence limits.

## Example Output

These are concise, sanitized excerpts based on existing hardware reports. They
omit device-identifying details such as MAC addresses; see the standalone
[healthy](examples/healthy_report.md) and
[defective](examples/defective_report.md) report excerpts.

**Healthy board** — successful recorded run:

```text
Overall status: PASS
Firmware tests: 7/7 PASS
Wi-Fi scan: 10 access point(s) detected
NVS: integrity verified
GPIO: output toggled five times
Flash diagnostics: chip_id PASS, flash_id PASS, flash_status PASS
Health score: 100/100 (HEALTHY)
```

**Defective board** — initial failed run:

```text
Overall status: ERROR
Firmware tests: no tests reported
Boot classification: INVALID_IMAGE
Boot evidence: invalid header: 0x3ffea272; RTCWDT_RTC_RESET
Flash diagnostics: chip_id PASS, flash_id PASS, flash_status PASS
Health score: 15/100 (DEFECTIVE)
```

## Architecture Diagram

```text
                 +----------------------+
                 |        ESP32         |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 | Validation Firmware  |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 |   Serial Protocol    |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 |     Host Runner      |
                 +----------+-----------+
                            |
          +-----------------+-----------------+
          |                 |                 |
          v                 v                 v
   +-------------+   +---------------+   +--------------+
   | Boot        |   | Flash         |   | Health       |
   | Analysis    |   | Diagnostics   |   | Scoring      |
   +------+------+   +-------+-------+   +------+-------+
          |                  |                  |
          +------------------+------------------+
                             |
                             v
                 +----------------------+
                 | JSON / Markdown /    |
                 | Raw Serial Reports   |
                 +----------------------+
```

## Repository Structure

```text
.
|-- firmware/
|   |-- esp32_test_firmware.ino
|   `-- encrypted_bootloader_support/  # IDF encryption-aware helper project
|-- examples/                           # sanitized excerpts from recorded reports
|-- host/
|   |-- bootlog_analyzer.py
|   |-- flash_validator.py
|   |-- report_generator.py
|   `-- test_runner.py
|-- reports/                            # local generated run evidence (ignored)
|-- sample_logs/                        # normal and failure log examples
|-- tests/
|   `-- test_host_framework.py
|-- .github/                            # issue and pull request templates
|-- platformio.ini
|-- requirements.txt
|-- PROJECT_AUDIT.md
|-- PROJECT_INVENTORY.md
|-- RECOVERY_ANALYSIS.md
|-- CONTRIBUTING.md
|-- SECURITY.md
`-- ROADMAP.md
```

The `.pio/` directory is PlatformIO/ESP-IDF build output and is excluded from
version control. `tests.zip` and `tests.7z` are existing archive snapshots;
their provenance and currentness should be checked before relying on them.

## Quick Start

From the project root, install the host dependencies, connect one ESP32 with
the validation firmware installed, then run:

```powershell
python -m pip install -r requirements.txt
python host\test_runner.py
```

The runner discovers likely ESP32 USB serial devices automatically. If
multiple likely devices are attached, specify one with `--port` rather than
letting the tool choose arbitrarily.

## Installation

Use Python 3.10 or newer and install host dependencies from the project root:

```powershell
python -m pip install -r requirements.txt
```

The host dependencies are `pyserial` for USB serial access/discovery and
`esptool` for chip and flash diagnostics. Install PlatformIO Core to build the
firmware. Connect one ESP32 board over USB, close any serial monitor that has
the port open, and ensure the test firmware is installed.

Build the diagnostic firmware with PlatformIO Core:

```powershell
platformio run
```

The included `platformio.ini` targets the classic ESP32 Dev Module and
configures DOUT flash mode at 40 MHz with the project's partition layout. These
settings were validated on the connected ESP32-D0WD-V3 with 4 MB BoyaMicro
flash; confirm compatibility before using this profile with a different board.

### Arduino IDE alternative

Open `firmware/esp32_test_firmware.ino` in Arduino IDE, select the appropriate
ESP32 board, and upload the sketch. The sketch uses 115200 baud and announces
`READY:esp32_test_firmware` after startup.

### Flash-encryption-enabled boards

The recovered COM6 board had flash encryption enabled. **Do not use
PlatformIO's ordinary `upload` target on an encryption-enabled board**: it
writes plaintext images, which cannot boot under the existing eFuse
configuration. The secure helper bootloader is configured with
`CONFIG_SECURE_FLASH_REQUIRE_ALREADY_ENABLED`; it does not enable flash
encryption or change eFuses.

For a board with the same already-enabled encryption and UART download
configuration, build the encryption-aware bootloader and Arduino application,
then write the bootloader, partition table, OTA selection record, and app with
esptool's `--encrypt` option. Replace `COM6` with the board's port:

```powershell
platformio run --project-dir firmware\encrypted_bootloader_support -e esp32dev
platformio run -e esp32dev

python -m esptool --chip esp32 --port COM6 --baud 115200 write-flash `
  --flash-mode dout --flash-freq 40m --flash-size 4MB --encrypt `
  0x1000 .pio\encrypted_bootloader_support\esp32dev\bootloader.bin `
  0x8000 .pio\build\esp32dev\partitions.bin `
  0xe000 "$env:USERPROFILE\.platformio\packages\framework-arduinoespressif32\tools\partitions\boot_app0.bin" `
  0x10000 .pio\build\esp32dev\firmware.bin
```

This command assumes flash encryption is already enabled, the device permits
encrypted UART downloads, and the project partition table matches the board.
It updates only the bootloader, partition table, OTA app0 selection record,
and app0 image ranges; it does not erase the entire flash. `boot_app0.bin`
comes with the installed Arduino-ESP32 PlatformIO package. esptool cannot
verify ciphertext by reading it back, so check the serial boot log and run the
test runner after flashing. **Never use this encrypted-flash command on an
unencrypted board.**

## Run Validation

With one likely ESP32 USB serial device connected, automatic detection selects
it:

```powershell
python host\test_runner.py
```

When your working directory is `host`, the equivalent command is:

```powershell
python test_runner.py
```

Override discovery when needed:

```powershell
python host\test_runner.py --port COM4
```

Detection recognizes common CP210/CP210x, CH340, FTDI, Espressif, and Silicon
Labs USB serial devices using their USB descriptions and vendor IDs. If more
than one likely device is found, the runner refuses to choose arbitrarily and
asks for `--port`.

Optional arguments are `--baud`, `--timeout`, `--boot-timeout`, and
`--report-dir`. Every invocation writes timestamped JSON and Markdown reports
plus `reports/raw_serial_log.txt` (or the corresponding path under
`--report-dir`). The raw log is overwritten by the latest run. It preserves
the captured serial stream for that test session; esptool output is included
separately in the JSON and Markdown flash-diagnostic sections.

Exit codes:

- `0` — firmware tests and hardware diagnostics passed
- `1` — a firmware test, flash diagnostic, or critical boot diagnostic failed
- `2` — the run is incomplete, such as a connection, dependency, timeout, or
  unavailable-diagnostic error

The 0–100 health score weights board information (15), GPIO (10), Wi-Fi (15),
NVS (15), memory (15), flash diagnostics (15), and boot diagnostics (15).
Scores classify as `HEALTHY` (80–100), `SUSPECT` (50–79), or `DEFECTIVE`
(0–49). The score is a transparent diagnostic heuristic, not a certification
of hardware reliability.

The serial command protocol is newline-terminated:

| Command | Response |
|---|---|
| `PING` | `PONG` |
| `RUN_TESTS` | `TEST_RESULT:` JSON records followed by a `TEST_SUMMARY:` JSON record |
| `HELP` | Lists supported commands |

Result records retain the original `name`, `status`, and `detail` fields; the
additional `data` object carries structured values. Tests cover serial
availability and heap readings; board model/revision, SDK version, flash size,
CPU frequency, MAC address, current and minimum free heap; Wi-Fi station-mode
scan; NVS write/read integrity in the dedicated `esp32_test` namespace; and
five software output blinks.

The LED pin uses `LED_BUILTIN` when the selected board defines it, otherwise
GPIO 2. Override it at compile time with `ESP32_TEST_LED_PIN` for boards wired
to a different LED pin. The GPIO result confirms software output toggling; it
cannot electrically verify the LED without external feedback. Wi-Fi PASS
requires at least one visible access point, so the test can fail in a shielded
or access-point-free environment. The NVS test uses a fixed key in its
dedicated namespace.

## Boot Diagnostics

Analyze a sample or captured log:

```powershell
python host\bootlog_analyzer.py sample_logs\normal_boot.log
python host\bootlog_analyzer.py sample_logs\watchdog_reset.log
python host\bootlog_analyzer.py sample_logs\invalid_header.log
```

The JSON output includes a classification and, for each recognized issue,
severity, likely causes, recommended actions, and matching log lines. Patterns
include invalid image headers (including `0x3ffea272`, `0x5691acba`, and
`0xd610e111`), `RTCWDT_RTC_RESET`, `POWERON_RESET`, `SW_RESET`,
`TG0WDT_SYS_RESET`, `TG1WDT_SYS_RESET`, `BROWNOUT_RESET`, flash read errors,
invalid all-ones flash IDs, Guru Meditation, panic, and `abort()`.

These findings are likely-cause diagnoses, not proof of a single root cause.
For example, invalid headers can result from an incorrect image/partition
offset, incompatible or corrupt flash contents, flash-encryption mismatch, or
flash/power instability. Repeated logs and electrical measurements help
distinguish them.

## Flash Diagnostics

After collecting firmware results, the runner executes esptool chip-ID,
flash-ID, and flash-status diagnostics. These commands reset the board into
its ROM bootloader; board auto-reset must work, or the operator may need to
hold BOOT during connection. The runner captures each command's output and
reports connection, packet, flash-read, and invalid flash-ID errors, including
messages such as `Failed to connect`, `No serial data received`, `A fatal
error occurred`, `invalid head of packet`, `flash read err`, `Manufacturer:
ff`, `Device: ffff`, and `invalid header`.

The offline image validator is separate from the on-board esptool checks:

```powershell
python host\flash_validator.py path\to\firmware.bin
```

It checks ESP image magic, segment boundaries, checksum, and an appended
SHA-256 digest when present. It does not flash the binary or establish that it
targets a particular ESP32 variant.

## Regression Tests

The host regression suite uses Python's standard `unittest` runner and mocks
serial/esptool interactions:

```powershell
python -m unittest discover -s tests -v
```

The tests cover boot patterns and advice, image validation, serial protocol
handling, esptool output parsing, port choice, report generation, and health
scoring. Physical validation still requires a connected ESP32, working
USB/bootloader auto-reset, a visible Wi-Fi access point for the Wi-Fi PASS
condition, and installed dependencies.

## Skills Demonstrated

**Embedded Systems**

- ESP32 firmware development
- GPIO validation
- Serial protocol design
- Flash diagnostics
- NVS validation

**Software Engineering**

- Python automation
- Automated testing
- Report generation
- CLI tool development
- Root-cause analysis

**Debugging & Investigation**

- Boot failure analysis
- Flash-encryption troubleshooting
- Hardware/firmware fault isolation
- Recovery validation

## Future Improvements

Potential follow-up work is tracked in [ROADMAP.md](ROADMAP.md). Near-term
opportunities include adding a CI workflow for host tests and linting, pinning
the PlatformIO platform/framework toolchain, broadening hardware-in-loop
coverage across ESP32 variants, and adding electrical feedback for GPIO/LED
validation. These are not claims of currently implemented functionality.

## Contributing

Bug reports, reproducible diagnostics, and focused pull requests are welcome.
Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or PR. Do not
include secrets, Wi-Fi credentials, or unredacted board-identifying data in
public logs or screenshots.

## License

This project is distributed under the [MIT License](LICENSE).
