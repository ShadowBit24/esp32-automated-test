# ESP32 Recovery Forensic Analysis

## Executive findings

- The 04:57 UTC report records repeated `invalid header: 0x3ffea272` and
  `RTCWDT_RTC_RESET`, no firmware tests, and passing chip-ID, flash-ID, and
  flash-status checks. Those three checks established ROM-bootloader
  communication and flash identification, not that the application image was
  readable or bootable.
- The strongest root-cause evidence is a flash-encryption mismatch. A prior
  eFuse inspection recorded flash encryption enabled (`FLASH_CRYPT_CNT=1`).
  Plaintext PlatformIO images did not boot. An encryption-aware IDF 6.1
  bootloader then logged an invalid partition-table magic number until the
  original table was rewritten with encrypted UART flashing. After the
  encrypted application and OTA selection record were written, the board
  reached `READY` and passed all tests.
- Firmware writes definitely occurred. The recorded esptool outputs show
  encrypted writes at offsets `0x1000`, `0x8000`, `0xe000`, and `0x10000`.
  The prior hardware session also records a PlatformIO upload and flash
  readback matching that build.
- **A full-chip erase cannot be conclusively ruled in or out.** No
  `erase_flash` command appears in the directly observed November 1 Copilot
  recovery commands. However, the PowerShell history contains multiple
  `erase_flash --force` and PlatformIO erase commands. That history file was
  last modified October 5, has no per-command timestamps or results, and
  therefore cannot establish whether any command ran successfully or whether
  it was part of this recovery.
- The selected PlatformIO board remains `esp32dev`. The project flash
  configuration changed to DOUT/40 MHz and an explicit partition file. The
  partition *layout* matches the table read from the board; the on-flash table
  sector was rewritten encrypted. The bootloader contents did change.
- Confidence is **high** that the encryption-aware bootloader, encrypted
  partition table, encrypted OTA selection record, and encrypted app write
  produced the observed recovery. Confidence is **undetermined** on whether a
  full-flash erase occurred at any point in the broader history.

## Time basis and evidence limits

The report generator records UTC. The workspace file modification times shown
by Windows are local time (America/New_York, UTC-04:00 on November 1, 2026).
Thus 04:57 UTC corresponds to 00:57 local, and 05:30 UTC to 01:30 local.

Evidence examined:

- Timestamped reports and serial captures in [`reports/`](./reports/).
- Current PlatformIO settings, firmware, partition CSV, secure-bootloader
  project, and generated binaries.
- Copilot session/tool execution records from the recovery work.
- VS Code logs under
  `C:\Users\nahiy\AppData\Roaming\Code\logs\20261101T001417`.
- PowerShell command history at
  `C:\Users\nahiy\AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt`.
- Arduino IDE log at
  `C:\Users\nahiy\AppData\Roaming\Arduino IDE\2026-10-22_log.log`.

The project directory is **not a Git repository**: both `git status` and
`git log` returned “not a git repository.” Consequently there is no project
commit history or Git diff to use as an independent change ledger. The VS Code
task log and text-model-change log for the November 1 session are empty; the
terminal log records shell-integration warnings, not command output. The
Arduino IDE logs examined are from October 22, not the November 1 recovery.
These absences limit attribution and chronology for commands entered outside
the recorded Copilot tool executions.

## Timeline

| Time (UTC; local) | Evidence | Reconstruction |
|---|---|---|
| 04:57:40; 00:57:40 | [`esp32_test_report_20261101_005740_403264.json`](./reports/esp32_test_report_20261101_005740_403264.json) | Initial recorded failure: `INVALID_IMAGE`, repeated `invalid header: 0x3ffea272`, and high-severity `RTC_WATCHDOG_RESET`. Firmware did not announce readiness; no firmware tests ran. Chip ID, flash ID, and flash status all passed. Health score 15/100. |
| 05:00–05:06; 01:00–01:06 | Reports `010028`, `010302`, and `010602` in [`reports/`](./reports/) | Invalid-image boot failures continued. The 05:06 report captures a different invalid header (`0x2e5af586`), showing the failure was not limited to one stable header value. Flash diagnostics continued to pass. |
| 05:10:17; 01:10:17 | [`esp32_test_report_20261101_011017_989599.json`](./reports/esp32_test_report_20261101_011017_989599.json) | Failure classification changed to `SW_RESET`; the firmware still did not reach readiness. The prior Copilot session records that ordinary DOUT/40 MHz uploading and subsequent encrypted-image experiments had not yet yielded a working application. |
| 05:20:50; 01:20:50 | [`esp32_test_report_20261101_012050_123984.json`](./reports/esp32_test_report_20261101_012050_123984.json) | Serial output identifies an **ESP-IDF 6.1.0** second-stage bootloader, then reports `partition 0 invalid magic number 0x9a2e`, “Failed to verify partition table,” and a partition-table load error. This is direct evidence that a different bootloader was running and that it could not interpret the then-current table contents in the encrypted-flash configuration. |
| 05:22:15; 01:22:15 | [`esp32_test_report_20261101_012215_164204.json`](./reports/esp32_test_report_20261101_012215_164204.json) | Bootloader now prints the valid partition table, loads app0 at `0x10000`, logs `flash encryption is enabled`, and the firmware emits `READY` plus all seven PASS test records. The host still reports ERROR because the firmware's `TEST_SUMMARY` JSON line is missing its closing brace. This was a protocol/reporting defect, not a boot failure. |
| 05:25:16; 01:25:16 | [`esp32_test_report_20261101_012516_031045.json`](./reports/esp32_test_report_20261101_012516_031045.json) | After fixing the summary JSON, the host reports PASS and health 100. The bootloader still warns that OTA data is invalid and falls back to trying partitions. |
| 05:30:38; 01:30:38 | [`esp32_test_report_20261101_013038_063011.json`](./reports/esp32_test_report_20261101_013038_063011.json) and [`raw_serial_log.txt`](./reports/raw_serial_log.txt) | After initializing OTA selection metadata for app0, the log contains no invalid-OTA-data warning. All seven firmware tests and all three flash diagnostics pass; health is 100/100, `HEALTHY`. Wi-Fi detects 10 APs. |

## Commands and flash operations

### Directly observed recovery commands

The following are the commands and operations recorded in the November 1
Copilot recovery session. Executable paths and workspace paths are shown
expanded for clarity; the interactive calls used PowerShell variables for
some of these paths.

**Builds and verification**

```powershell
C:\Users\nahiy\.platformio\penv\Scripts\platformio.exe run --project-dir C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\firmware\encrypted_bootloader_support -e esp32dev
C:\Users\nahiy\.platformio\penv\Scripts\platformio.exe run --project-dir C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test -e esp32dev
C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m esptool --chip esp32 image-info C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\.pio\build\esp32dev\firmware.bin
C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m esptool --chip esp32 image-info C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\firmware\encrypted_bootloader_support\.pio\build\esp32dev\bootloader.bin
C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m esptool --chip esp32 --port COM6 --baud 115200 read-flash 0x8000 0x1000 C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\reports\partition_table_readback.bin
C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\nahiy\.platformio\packages\framework-espidf\components\partition_table\gen_esp32part.py C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\reports\partition_table_readback.bin
C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m esptool --chip esp32 partition-table C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\reports\partition_table_readback.bin
C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m unittest discover -s C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\tests -v
```

The helper and Arduino builds succeeded. A first Arduino rebuild failed after
the nested IDF build files were included in the Arduino source tree; the
source filter/build-directory configuration was corrected and both builds
then succeeded. The esptool `partition-table` subcommand attempt failed with
“No such command”; the IDF `gen_esp32part.py` command above decoded and
validated the table. The offline suite passed 13 tests.

**Observed encrypted writes to COM6**

```powershell
C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m esptool --chip esp32 --port COM6 --baud 115200 write-flash --flash-mode dout --flash-freq 40m --flash-size 4MB --encrypt 0x1000 C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\firmware\encrypted_bootloader_support\.pio\build\esp32dev\bootloader.bin

C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m esptool --chip esp32 --port COM6 --baud 115200 write-flash --flash-mode dout --flash-freq 40m --flash-size 4MB --encrypt 0x8000 C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\reports\partition_table_readback.bin

C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m esptool --chip esp32 --port COM6 --baud 115200 write-flash --flash-mode dout --flash-freq 40m --flash-size 4MB --encrypt 0x10000 C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\.pio\build\esp32dev\firmware.bin

C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m esptool --chip esp32 --port COM6 --baud 115200 write-flash --flash-mode dout --flash-freq 40m --flash-size 4MB --encrypt 0xe000 C:\Users\nahiy\.platformio\packages\framework-arduinoespressif32\tools\partitions\boot_app0.bin
```

The esptool outputs report successful writes: 28,288 bytes at `0x1000`,
4,096 bytes at `0x8000`, 742,848 bytes at `0x10000`, and 8,192 bytes at
`0xe000`. esptool explicitly warned it could not verify data readback while
writing encrypted flash. These writes necessarily erase the sectors they
replace; they are **not** `erase_flash` and do not imply a full-chip erase.

The runner was invoked repeatedly against COM6:

```powershell
C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\host\test_runner.py --port COM6 --report-dir C:\Users\nahiy\Documents\PlatformIO\Projects\esp32-automated-test\reports
```

For each completed runner invocation, it also launched these esptool
diagnostics (the exact invocation list is retained in each report's
`flash_diagnostics[].command` field):

```powershell
C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m esptool --port COM6 --baud 115200 chip-id
C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m esptool --port COM6 --baud 115200 flash-id
C:\Users\nahiy\AppData\Local\Python\pythoncore-3.14-64\python.exe -m esptool --port COM6 --baud 115200 read-flash-status
```

The directly observed November 1 Copilot recovery commands contain no
`erase_flash`, `erase-region`, or eFuse-write operation. The initial ordinary
PlatformIO upload is recorded in the preceding hardware-session notes as
successful and its image bytes were read back for comparison; its full command
line is not retained in the current workspace logs. The encrypted esptool
application write above independently proves that a firmware upload occurred.

### PowerShell history: erase and upload entries with no reliable date/result

The separate PSReadLine history file has filesystem modification time
**2026-10-05 18:45:04** and no per-command timestamps, process exit codes, or
esptool output. It contains these relevant entries (line numbers refer to
that file):

- Lines 50–51: `pio run -t erase` and `platformio.exe run --target erase`.
- Lines 55, 56, 57, 58, and 61: `esptool ... erase_region` attempts targeting
  `0x0000` through `0x10000` or `0x20000`.
- Lines 65, 84, 86, 94, 96, and 100: `esptool.py --port COM6 erase_flash
  --force`.
- Lines 59, 63, 67, 85, 87, 98, 102, 107, and 109:
  `platformio.exe run --target upload`.
- Lines 69, 71, 72, 77, 79, and 82: raw `write_flash` attempts with various
  DIO/DOUT and frequency settings. Examples include:

```powershell
... esptool.py --port COM6 --baud 115200 write_flash -z --flash_mode dio --flash_freq 40m 0x1000 .pio/build/esp32dev/bootloader.bin 0x8000 .pio/build/esp32dev/partitions.bin 0x10000 .pio/build/esp32dev/firmware.bin
... esptool.py --port COM6 --baud 115200 write_flash -z --flash_mode dout --flash_freq 20m 0x0000 .pio/build/esp32dev/bootloader.bin 0x8000 .pio/build/esp32dev/partitions.bin 0x10000 .pio/build/esp32dev/firmware.bin
... esptool.py --port COM6 --baud 115200 write_flash -z --flash_mode dout --flash_freq 40m 0x1000 .pio/build/esp32dev/bootloader.bin 0x8000 .pio/build/esp32dev/partitions.bin 0x10000 .pio/build/esp32dev/firmware.bin
```

The history also contains `espefuse.py --port COM6 set_flash_voltage 3.3V`
at lines 74, 76, and 104. These entries have no outcome or timestamp either.
PSReadLine history is evidence that commands were entered into a shell, not
proof that they completed successfully or that they were run during the
November 1 recovery. The stale history therefore prevents a definitive
whole-device-erasure or eFuse-change conclusion for the broader machine
history.

## Settings and files

### Board/build configuration

Current [`platformio.ini`](./platformio.ini):

- `board = esp32dev` (unchanged target in the final configuration).
- `board_build.flash_mode = dout`.
- `board_build.f_flash = 40000000L` (40 MHz).
- `board_build.partitions =
  firmware/encrypted_bootloader_support/partitions.csv`.
- `build_src_filter = +<*> -<encrypted_bootloader_support/>`.

The prior hardware-session record says DIO/40 MHz and DOUT/20 MHz were tested
before returning to DOUT/40 MHz. The stale PowerShell history independently
contains DIO/40 MHz, DOUT/20 MHz, and DOUT/40 MHz write commands, but cannot
timestamp them to this recovery. The final ROM/bootloader log confirms DOUT
and 40 MHz.

The custom partition CSV specifies:

| Partition | Offset | Size |
|---|---:|---:|
| nvs | `0x9000` | `0x5000` |
| otadata | `0xe000` | `0x2000` |
| app0 | `0x10000` | `0x140000` |
| app1 | `0x150000` | `0x140000` |
| spiffs | `0x290000` | `0x160000` |
| coredump | `0x3f0000` | `0x10000` |

The table decoded from the board at `0x8000` had these same entries and
offsets. Thus the configured **layout** was not a new layout, although the
partition-table sector was later rewritten encrypted. The secure helper
project enables flash encryption support and sets
`CONFIG_SECURE_FLASH_REQUIRE_ALREADY_ENABLED=y`; the running log says
`flash encryption is enabled`. The bootloader contents were replaced: the
successful encrypted write targeted `0x1000`, and the subsequent boot log
identifies an ESP-IDF 6.1.0 second-stage bootloader. The Arduino application
still identifies its SDK as ESP-IDF 4.4.7.

### Workspace changes and generated artifacts

File modification times are local time:

| Path | Last modified | Relevance |
|---|---|---|
| [`firmware/encrypted_bootloader_support/sdkconfig.defaults`](./firmware/encrypted_bootloader_support/sdkconfig.defaults), [`partitions.csv`](./firmware/encrypted_bootloader_support/partitions.csv), [`main/main.c`](./firmware/encrypted_bootloader_support/main/main.c) | 01:15 | Added encryption-aware IDF bootloader project configuration, partition layout, and guarded test app. |
| [`firmware/esp32_test_firmware.ino`](./firmware/esp32_test_firmware.ino) | 01:22 | Fixed the missing closing brace in `TEST_SUMMARY` JSON. |
| [`platformio.ini`](./platformio.ini) | 01:25 | Final DOUT/40 MHz profile, explicit partition file, and nested-project source exclusion. |
| `.pio/build/esp32dev/firmware.bin` | 01:26 | Arduino application image, 742,848 bytes. |
| `.pio/encrypted_bootloader_support/esp32dev/bootloader.bin` | 01:28 | IDF 6.1 encryption-aware bootloader build artifact, 28,288 bytes. |
| [`reports/raw_serial_log.txt`](./reports/raw_serial_log.txt) | 01:30 | Final successful hardware boot and firmware output. |
| [`README.md`](./README.md), [`PROJECT_AUDIT.md`](./PROJECT_AUDIT.md) | 01:30 | Updated flashing safety guidance and recorded hardware follow-up. |

The final report artifacts and all other generated reports are retained in
[`reports/`](./reports/). The temporary partition-table readback binary was
removed after decoding and using it for the encrypted write.

Selected SHA-256 values for the current on-disk files:

| File | SHA-256 |
|---|---|
| `.pio/build/esp32dev/firmware.bin` | `6F94DA8A5FFA43585090EDBED844E194D8ED08AA783E513EF3B4A0145186B6B8` |
| `.pio/build/esp32dev/partitions.bin` | `148B959CBFF1C38AA8E1D5C0BA9D612C54997B945E56A63F41223EEF650653A1` |
| `.pio/encrypted_bootloader_support/esp32dev/bootloader.bin` | `4E527AE48EA4BD1B9A56364506232C0EE6332D45E4B872B0DF08625D7345516A` |
| [`reports/esp32_test_report_20261101_005740_403264.json`](./reports/esp32_test_report_20261101_005740_403264.json) | `20BE82E1D15F949B89398642067EE0D7B1438ED9C06DCAE635B166C083DCBFD0` |
| [`reports/esp32_test_report_20261101_013038_063011.json`](./reports/esp32_test_report_20261101_013038_063011.json) | `B7D715BFE8095DBF726AFB97735574CC0927BF9A5FCD86C3A87028C94CF93F11` |

These are hashes of current build outputs, not proof of byte-for-byte identity
with encrypted on-device contents; esptool reported that encrypted readback
verification was unavailable.

### Arduino IDE and VS Code logs

The Arduino IDE log dated October 22 records COM6 and prior upload/configuration
activity, including an ESP32 profile with `FlashFreq=80`,
`FlashMode=qio`, `PartitionScheme=default`, and `EraseFlash=none`; a later
profile entry has `FlashMode=dio`. It also contains an uploader process error
on October 22. These records predate the November 1 recovery by ten days and
do not establish the settings or erase behavior of the November 1 writes. No
Arduino IDE log modified on November 1 was found.

The November 1 VS Code `tasks.log` and `textModelChanges.log` are zero bytes.
The terminal log contains shell-integration timeout warnings but no captured
esptool transcript. Therefore no Arduino IDE upload is evidenced for the
04:57–05:30 UTC recovery interval; the observed recovery writes were PlatformIO
builds and esptool commands.

## Conclusions and confidence

| Question | Conclusion | Confidence |
|---|---|---|
| Most likely original root cause | Flash encryption was already enabled, while plaintext PlatformIO images were being placed in flash. ROM invalid-header output is consistent with encrypted bytes being interpreted as an unencrypted boot image; changing flash mode alone did not resolve it. The later encrypted boot path and active-encryption boot log directly support this explanation. | **High (0.95)** |
| Most likely recovery mechanism | Wrote an encryption-aware IDF 6.1 bootloader at `0x1000`, rewrote the existing partition table encrypted at `0x8000`, wrote app0 encrypted at `0x10000`, and wrote the Arduino package's app0 OTA-selection record encrypted at `0xe000`. The board then loaded app0 and passed the test suite. | **High (0.95)** |
| Did firmware get uploaded? | **Yes.** Successful esptool output records 742,848 bytes written encrypted to app0. The preceding Copilot hardware session also records a successful ordinary PlatformIO upload; the exact earlier command line is not recoverable from the retained VS Code/task logs. | **Certain for the encrypted app write (1.0); high for earlier PlatformIO upload (0.9)** |
| Was `erase_flash` executed successfully during November 1 recovery? | No such command appears in the directly observed Copilot recovery operations. The stale PowerShell history contains multiple `erase_flash --force` and PlatformIO erase entries, but no timestamps or outcomes. Whether a full-chip erase occurred in the broader history is **undetermined**. | **High** that Copilot's recorded recovery did not issue it; **undetermined** for overall machine/board history |
| Did flash mode change? | The final build and boot log use DOUT/40 MHz. Earlier DIO/40 and DOUT/20 experiments are recorded in prior-session notes/history, but their chronology relative to the 04:57 report is not independently timestamped. | **High** for final setting; **medium** for earlier experiments |
| Did partition settings change? | The PlatformIO configuration now explicitly names the custom CSV. The table entries/offsets match the table read from the board, so there is no evidenced logical layout change; the table sector was rewritten in encrypted form. | **High (0.9)** |
| Did board target/settings change? | Final PlatformIO target remains `esp32dev`; flash size is 4 MB, DOUT, 40 MHz. These are host build settings. No board identity change is evidenced. Stale shell history contains `set_flash_voltage 3.3V` commands without outcomes, so a global claim that no prior eFuse setting was ever changed would exceed the evidence. | **High** for final project settings; **undetermined** for stale eFuse command outcomes |
| Did bootloader contents change? | **Yes.** esptool successfully wrote the secure bootloader at `0x1000`, and the subsequent serial log identifies ESP-IDF 6.1.0 as the running second-stage bootloader. | **High (0.98)** |

The flash-ID, chip-ID, and flash-status PASS results in the initial report do
not contradict this diagnosis: those commands reached the ROM bootloader and
identified the chip/flash, but they did not validate the contents or encryption
state of the application image.
