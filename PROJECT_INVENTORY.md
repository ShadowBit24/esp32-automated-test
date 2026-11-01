# ESP32 Automated Test Workspace Inventory

## Scope and current state

This inventory covers the complete workspace at the time of inspection. The
workspace contains **2,123 files totaling about 188.4 MB**. The `.pio/` build
tree accounts for 2,066 files and about 186.0 MB; it is generated build output,
not handwritten project source. Outside `.pio/`, the workspace contains 57
files, including Python bytecode caches and generated hardware reports.

The latest recorded board report,
[`reports/esp32_test_report_20261101_013038_063011.json`](./reports/esp32_test_report_20261101_013038_063011.json),
is PASS with 7/7 firmware tests, 3/3 flash diagnostics, and health 100/100.
This is a recorded hardware run, not a repeatability guarantee.

The directory is not a Git repository: `git status` and `git log` report that
no `.git` repository exists. The inventory therefore describes filesystem
contents, not tracked/untracked status or a commit history. No files other
than this requested inventory were changed.

## 1. Repository tree

`[generated]` marks build output, interpreter caches, reports, or packaged
snapshots rather than active source. `.pio` is shown by major output family
because it contains more than two thousand compiler/build-system files.

```text
esp32-automated-test/
|-- .pio/                                      [generated; 2,066 files, ~186.0 MB]
|   |-- build/esp32dev/
|   |   |-- bootloader.bin, partitions.bin, firmware.bin
|   |   |-- firmware.elf, firmware.map
|   |   |-- FrameworkArduino/                  [.o, .d and framework objects]
|   |   |-- lib55d/Preferences/
|   |   |-- lib8c0/WiFi/
|   |   `-- linker, SCons and dependency metadata
|   `-- encrypted_bootloader_support/esp32dev/
|       |-- bootloader.bin, firmware.bin, partitions.bin
|       |-- config/, bootloader/, esp-idf/, CMake/Ninja output
|       `-- encrypted flash argument files
|-- firmware/
|   |-- esp32_test_firmware.ino
|   `-- encrypted_bootloader_support/
|       |-- CMakeLists.txt
|       |-- main/
|       |   |-- CMakeLists.txt
|       |   `-- main.c
|       |-- partitions.csv
|       |-- platformio.ini
|       |-- sdkconfig.defaults
|       `-- sdkconfig.esp32dev                 [generated configuration snapshot]
|-- host/
|   |-- bootlog_analyzer.py
|   |-- flash_validator.py
|   |-- report_generator.py
|   |-- test_runner.py
|   `-- __pycache__/                            [generated Python bytecode]
|-- reports/
|   |-- .gitkeep
|   |-- esp32_test_report_*.json                [12 timestamped reports]
|   |-- esp32_test_report_*.md                  [12 timestamped reports]
|   `-- raw_serial_log.txt                      [latest run; overwritten]
|-- sample_logs/
|   |-- invalid_header.log
|   |-- normal_boot.log
|   `-- watchdog_reset.log
|-- tests/
|   |-- test_host_framework.py
|   `-- __pycache__/                            [generated Python bytecode]
|-- tests.zip                                   [source/test snapshot; includes bytecode]
|-- tests.7z                                   [archive; contents not decoded here]
|-- platformio.ini
|-- requirements.txt
|-- README.md
|-- PROJECT_AUDIT.md
|-- RECOVERY_ANALYSIS.md
`-- PROJECT_INVENTORY.md                         [this document]
```

The tagged path
`.pio/build/esp32dev/FrameworkArduino/Esp.cpp.d` is generated compiler
dependency metadata for the Arduino framework's `Esp.cpp` object. It lists
included headers for dependency tracking; it is not firmware source.

## 2. Source and project file purposes

### Firmware and build configuration

| File | Purpose |
|---|---|
| [`firmware/esp32_test_firmware.ino`](./firmware/esp32_test_firmware.ino) | Arduino application, serial command protocol, JSON result records, board information, heap, Wi-Fi scan, Preferences/NVS integrity check, and five software LED-pin toggles. |
| [`platformio.ini`](./platformio.ini) | Root PlatformIO Arduino environment, board ID `esp32dev`, DOUT/40 MHz settings, custom partition file, source filter excluding the nested IDF project, and serial speeds. |
| [`firmware/encrypted_bootloader_support/platformio.ini`](./firmware/encrypted_bootloader_support/platformio.ini) | Separate PlatformIO ESP-IDF build for the encryption-aware helper bootloader; puts generated output under root `.pio/encrypted_bootloader_support`. |
| [`firmware/encrypted_bootloader_support/CMakeLists.txt`](./firmware/encrypted_bootloader_support/CMakeLists.txt) | ESP-IDF project definition. |
| [`firmware/encrypted_bootloader_support/main/CMakeLists.txt`](./firmware/encrypted_bootloader_support/main/CMakeLists.txt) | Registers the helper application's `main.c` component. |
| [`firmware/encrypted_bootloader_support/main/main.c`](./firmware/encrypted_bootloader_support/main/main.c) | Small ESP-IDF app that checks flash encryption state and logs success; aborts if encryption is not enabled. It is not the Arduino test firmware. |
| [`firmware/encrypted_bootloader_support/partitions.csv`](./firmware/encrypted_bootloader_support/partitions.csv) | NVS, OTA metadata, app0/app1, SPIFFS, and coredump partition layout used by the projects. |
| [`firmware/encrypted_bootloader_support/sdkconfig.defaults`](./firmware/encrypted_bootloader_support/sdkconfig.defaults) | IDF defaults enabling flash-encryption-aware boot support, requiring encryption already be enabled, and selecting DOUT/40 MHz/4 MB. |
| [`firmware/encrypted_bootloader_support/sdkconfig.esp32dev`](./firmware/encrypted_bootloader_support/sdkconfig.esp32dev) | Large generated IDF 6.1 configuration snapshot. This is generated configuration rather than concise source configuration; see configuration drift under technical debt. |

### Host software and tests

| File | Purpose |
|---|---|
| [`host/test_runner.py`](./host/test_runner.py) | Main host orchestrator: detects/selects serial ports, waits for READY, sends `RUN_TESTS`, validates JSON records, runs esptool chip/flash/status commands, scores board health, and writes reports. |
| [`host/bootlog_analyzer.py`](./host/bootlog_analyzer.py) | Recognizes reset, watchdog, image-header, flash-read, panic, abort, and invalid flash-ID patterns; produces severity, likely causes, recommended actions, and a CLI JSON result. |
| [`host/flash_validator.py`](./host/flash_validator.py) | Offline parser for ESP image magic, segment boundaries, checksum, and appended SHA-256; it does not flash or establish hardware compatibility. |
| [`host/report_generator.py`](./host/report_generator.py) | Writes timestamped JSON and Markdown plus the stable `raw_serial_log.txt` file. |
| [`tests/test_host_framework.py`](./tests/test_host_framework.py) | `unittest` regression suite for analyzer patterns, image validation, mocked serial protocol, esptool output classification, port choice, report generation, and scoring. |
| [`requirements.txt`](./requirements.txt) | Declares `pyserial>=3.5` and `esptool>=4.7`; no upper bounds or lock file. |

### Documentation, data, and generated evidence

| File or group | Purpose |
|---|---|
| [`README.md`](./README.md) | Setup, protocol, hardware test behavior, encrypted-flash workflow, CLI commands, and limitations. |
| [`PROJECT_AUDIT.md`](./PROJECT_AUDIT.md) | Initial gap analysis and historical implementation/hardware verification notes. Some early audit sections describe pre-upgrade state; use the post-implementation section for later status. |
| [`RECOVERY_ANALYSIS.md`](./RECOVERY_ANALYSIS.md) | Forensic timeline of the encryption-related recovery, observed commands, evidence limits, and confidence ratings. |
| `sample_logs/normal_boot.log` | Small normal boot and legacy three-test protocol sample. |
| `sample_logs/invalid_header.log` | Sample ROM log with invalid image headers and RTC watchdog reset. |
| `sample_logs/watchdog_reset.log` | Sample TG1/task-watchdog reset log. |
| `reports/esp32_test_report_*.json` (12 files) | Machine-readable historical hardware runs, including failures and final passes. |
| `reports/esp32_test_report_*.md` (12 files) | Human-readable renderings of those runs. |
| `reports/raw_serial_log.txt` | Raw serial capture for the most recent report; overwritten by subsequent runner invocations. |
| `reports/.gitkeep` | Keeps the otherwise generated-report directory present. |
| `tests.zip` | Packaged snapshot containing source, docs, test code, and `__pycache__`; it predates the final inventory and does not include `RECOVERY_ANALYSIS.md`. |
| `tests.7z` | Additional archive snapshot. A 7-Zip decoder was unavailable, so its member list/content was not verified. |
| `host/__pycache__/*`, `tests/__pycache__/*` | Python bytecode caches, not source. |
| `.pio/build/esp32dev/FrameworkArduino/Esp.cpp.d` and other `.d` files | Compiler dependency manifests generated during build. |
| Other `.pio` `.o`, `.a`, `.elf`, `.map`, `.bin`, CMake/Ninja/SCons files | Compiled objects, libraries, firmware images, symbol/debug/link outputs, and build-system state. |

## 3. Architecture overview

```text
ESP32 ROM boot output
        |
        v
host/test_runner.py -- pyserial serial protocol
        |                         |
        | READY / RUN_TESTS       +--> firmware/esp32_test_firmware.ino
        | TEST_RESULT JSON              board tests and TEST_SUMMARY JSON
        |
        +--> bootlog_analyzer.py
        +--> esptool chip-id / flash-id / read-flash-status
        +--> health scoring
        `--> report_generator.py
                  |--> reports/*.json
                  |--> reports/*.md
                  `--> reports/raw_serial_log.txt

flash_validator.py: independent offline ESP image file validation

Separate build/deployment path:
encrypted_bootloader_support (ESP-IDF 6.1) -> encryption-aware bootloader
root PlatformIO project (Arduino-ESP32 / IDF 4.4.7) -> test application
```

The Arduino serial interface keeps newline-delimited commands (`PING`,
`RUN_TESTS`, `HELP`), `READY:esp32_test_firmware`, `TEST_RESULT:` JSON records,
and a `TEST_SUMMARY:` JSON record. The runner parses the serial result stream,
then executes ROM-bootloader diagnostics using esptool. Boot analysis combines
captured boot output with diagnostic output in the final report. The image
validator is independent of board connection and of esptool flashing.

The secure helper is a separate ESP-IDF 6.1 project; the running Arduino
firmware reports ESP-IDF 4.4.7. Its purpose is to let an already
flash-encryption-enabled ESP32 load encrypted flash contents. It is not a
general-purpose replacement for a secure production boot chain.

## 4. Dependencies

### Host runtime

- Python 3.10+ as documented in README; the hardware session used Python 3.14.
- Python standard library: `argparse`, `hashlib`, `json`, `pathlib`,
  `subprocess`, `unittest`, `typing`, and related modules.
- `pyserial>=3.5`: serial ports and port enumeration.
- `esptool>=4.7`: chip ID, flash ID, flash status, and encrypted writes.

No Python lock file, virtual-environment declaration, packaging metadata, or
declared test dependency exists. Lower bounds permit dependency versions and
CLI behavior to change over time.

### Firmware/build toolchains

- PlatformIO Core and the `espressif32` platform.
- Root Arduino environment uses Arduino-ESP32 2.0.17 and ESP-IDF 4.4.7 in the
  recorded hardware build.
- Secure helper environment uses ESP-IDF 6.1.0.
- Xtensa ESP32 compiler, CMake/Ninja, PlatformIO esptool integration, Arduino
  `WiFi` and `Preferences` libraries.

The version numbers above are observed in existing build output/reports;
`platformio.ini` does not pin the platform or framework package versions.

## 5. Entry points

| Entry point | Invocation or trigger | Role |
|---|---|---|
| `host/test_runner.py` | `python host\test_runner.py [--port COMx]` | Primary complete host validation CLI. |
| `host/bootlog_analyzer.py` | `python host\bootlog_analyzer.py <log-file>` | Standalone boot-log classification CLI. |
| `host/flash_validator.py` | `python host\flash_validator.py <image.bin>` | Standalone offline image validator CLI. |
| Firmware `setup()` / `loop()` | ESP32 reset, then serial command | Announces board and READY; processes serial commands; executes tests on `RUN_TESTS`. |
| `tests/test_host_framework.py` | `python -m unittest discover -s tests -v` | Offline host regression suite. |
| Root PlatformIO environment | `platformio run` | Builds the Arduino test firmware. |
| Secure helper PlatformIO environment | `platformio run --project-dir firmware\encrypted_bootloader_support -e esp32dev` | Builds the encryption-aware IDF helper/bootloader. |

The README documents a normal PlatformIO upload for ordinary boards and a
separate encrypted esptool workflow for the connected encrypted board. Those
are different deployment paths and must not be interchanged.

## 6. Test framework description

The project has one host test module using Python's standard `unittest`
framework. It contains **13 test methods** grouped into analyzer, image
validator, and runner tests. Hardware access is mocked; serial responses,
esptool subprocess results, port selection, report creation, and score output
are tested without an ESP32.

The tests cover requested reset classifications and actionable fields,
invalid flash IDs, legacy analyzer behavior, a synthesized valid ESP image
and bad magic, JSON serial protocol/report shape, esptool failure text,
port selection/ambiguity, incomplete-run reporting, confirmed boot failure,
and report sections/health score.

The test suite has no coverage measurement, CI workflow, linter/type checker,
or hardware-in-loop test harness. It does not exercise actual encrypted
flashing, bootloader compatibility, eFuse prerequisites, real serial buffering,
RF variability, or electrical GPIO behavior. At the previous validated
session, all 13 host tests passed; this inventory task did not make code
changes or rerun them.

## 7. Coverage gaps

- No automated check that the packaged `tests.zip`/`tests.7z` snapshots match
  the workspace source or are current.
- No complete test for the three checked-in sample logs as files; analyzer
  coverage primarily uses constructed strings.
- No tests for malformed/oversized JSON, serial disconnects mid-record,
  arbitrary Unicode/control bytes, or long/noisy real boot streams.
- Port detection heuristics are not verified against a broad set of USB VID/PID
  and descriptions; USB bridge detection is only a likely-device heuristic.
- No hardware tests validate actual flash encryption, encrypted UART policy,
  board-specific partition map, flash contents, chip revisions, or recovery
  behavior.
- `flash_validator.py` has only two direct tests (valid synthetic image and
  invalid magic); image variants, truncations at each field, checksum/hash
  boundaries, segment limits, padding, and malformed metadata lack broad
  coverage.
- No test confirms Wi-Fi scans complete asynchronously or distinguishes a
  scan error from a completed scan with zero visible APs in all library
  versions.
- The NVS test does not test preexisting-key restoration, power loss during
  writes, NVS wear, or concurrent use.
- GPIO PASS records software writes, not physical LED output, pin wiring,
  voltage, or current.
- Health scoring thresholds and weights are not calibrated against known
  defective boards; a numeric 100 is a heuristic, not a reliability
  certification.
- No test validates report retention, concurrent invocations, file permission
  policy, or path behavior when report directories are unwritable.
- No regression test builds either PlatformIO environment in CI or checks
  cross-version Arduino/IDF bootloader compatibility.

## 8. Technical debt

- **Generated-file pollution:** `.pio/` contains 2,066 files and ~186 MB,
  including the tagged `.d` dependency file, object files, ELF/map artifacts,
  dependency manifests, and CMake/Ninja state. Python `__pycache__` directories
  also reside in the workspace.
- **No ignore policy:** no `.gitignore` or `.git` directory is present. If this
  is initialized as a Git project, generated binaries, report files, and
  caches are at risk of accidental inclusion.
- **Generated configuration in source tree:** `sdkconfig.esp32dev` is a
  90-KB generated IDF config, while `sdkconfig.defaults` is the intended
  compact source of selected defaults. It contains both the effective
  `CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"` and the generic
  `CONFIG_PARTITION_TABLE_FILENAME="partitions_singleapp.csv"` selector. The
  built/read-back partition table matches the custom CSV, so the generic
  selector alone is not evidence that the wrong table was used. Keep the
  generated snapshot out of the role of source-of-truth and validate effective
  settings when regenerating builds.
- **Duplicated snapshots:** `tests.zip` embeds a previous source tree and
  Python bytecode; it omits later documentation. `tests.7z` is an additional
  opaque archive. These duplicate sources can become stale and make it unclear
  which copy is authoritative.
- **Unbounded reports:** each invocation retains timestamped JSON/Markdown
  while overwriting only the stable raw-log file. Large boot streams are
  repeated in JSON and Markdown and can grow report storage quickly.
- **Long procedural host script:** `test_runner.py` is about 684 lines and
  combines discovery, serial protocol, subprocess execution, scoring,
  orchestration, CLI, and verdict logic.
- **Hand-built JSON in C++:** firmware composes nested JSON through `String`
  concatenation and manually escapes detail strings; protocol correctness
  depends on maintaining matching delimiters and escaping rules.
- **Protocol/test contract duplication:** expected test names are listed in
  the host runner and separately emitted in firmware and test mocks. These can
  drift.
- **Build reproducibility:** PlatformIO platform/framework versions and Python
  dependency versions are not locked; the two ESP-IDF generations are not
  pinned explicitly in a manifest beyond current local build state.
- **Historical docs:** `PROJECT_AUDIT.md` includes an initial audit snapshot
  whose pre-implementation descriptions remain in the document. Later status
  exists, but readers must distinguish historical findings from current state.
- **Cross-platform assumptions:** README examples target PowerShell and
  Windows paths; scripts are Python but portability is not tested.

## 9. Security concerns

- The secure helper configuration uses **flash-encryption development mode**
  and allows encrypted UART bootloader downloads. `REQUIRE_ALREADY_ENABLED`
  prevents the helper from turning encryption on, but does not make
  development-mode UART access equivalent to a production locked-down device.
- Flash encryption is not the same as secure boot. The checked-in sdkconfig
  indicates secure-boot capability support, but no enabled secure-boot
  configuration/signing workflow was identified. Firmware authenticity and
  rollback protection should not be inferred from encryption alone.
- The README contains an encrypted flashing command that changes bootloader,
  partition table, OTA metadata, and application ranges. It is board-state
  dependent and can make a device unbootable if applied to a board with
  different eFuse/partition settings. The documentation warns against using
  it on unencrypted boards; operational preflight checks remain manual.
- Test reports expose the board MAC address and detailed serial boot output.
  Treat reports and raw logs as device-identifying data; avoid publishing
  them unredacted.
- Serial commands have no authentication. They are intended for a physically
  connected local validation setup, not an untrusted remote serial bridge.
- The NVS test writes a fixed key in the `esp32_test` namespace and removes
  that key at the end. On a device using the same namespace/key for unrelated
  data, the test can overwrite and delete an existing value.
- Host tools execute the installed `esptool` module and write reports to the
  selected directory. Dependencies are not locked, and user-provided report
  paths/content should be treated as local trusted inputs.
- No private encryption key was found in the enumerated project sources;
  board-bound eFuse key material is not stored in the workspace.

## 10. Maintainability concerns

- No repository history, CI, contribution guidance, or reproducible bootstrap
  beyond README commands is available.
- The current source archive and generated configuration snapshots complicate
  review because the workspace contains multiple copies of project state.
- Hardware and host behaviors are coupled in one runner; the protocol schema
  is implicit rather than versioned or documented as a standalone contract.
- Health scoring does not document calibration evidence and can overstate
  certainty when tests are environment-dependent or only software-observed.
- The root README describes general Arduino IDE upload, but the connected
  encrypted board specifically requires the custom encrypted workflow. The
  distinction is present, yet the generic upload wording can still be
  misapplied without careful reading.
- Build and runtime versions in reports and binaries can differ from future
  locally installed versions because manifests do not pin them.
- Hardware-specific values (GPIO pin, flash parameters, board profile) need
  clear separation between this tested board and a reusable framework default.

## 11. Suggested improvements

1. Add `.gitignore` rules for `.pio/`, `__pycache__/`, `*.py[cod]`, and
   generated report outputs while deliberately deciding which sample evidence
   should be versioned.
2. Keep one authoritative test source; remove or regenerate archive snapshots
   and exclude bytecode/generated sdkconfig from distribution unless required.
3. Reconcile `sdkconfig.esp32dev` with `sdkconfig.defaults`, custom partition
   selection, and actual PlatformIO build output; document which file is
   authoritative.
4. Pin PlatformIO platform/framework and Python dependency versions, and add a
   clean-environment build/test workflow.
5. Add CI for Python unit tests, syntax/lint/type checks, image-validator edge
   cases, and both build configurations where toolchains are available.
6. Add hardware-in-loop tests for encrypted boot, board identity, partition
   layout, OTA selection, serial reconnect behavior, and test-result schemas.
7. Preserve and restore any previous NVS test key/value, or use a unique
   temporary key/namespace with explicit cleanup semantics.
8. Treat GPIO as a software-toggle check unless an external feedback sensor is
   present; label the result accordingly in reports and scoring.
9. Document score weights, thresholds, missing-data behavior, and environmental
   dependencies; avoid presenting the score as certification.
10. Add report retention/size controls and consider redacting MAC addresses
    before sharing diagnostics.
11. Split the host runner into focused protocol, diagnostics, scoring, and CLI
    modules only if the existing surface continues to grow; first add tests
    around current behavior.
12. For production-secure deployments, separately evaluate secure boot,
    anti-rollback, release-mode encryption, UART download restrictions, signed
    artifacts, recovery procedures, and key lifecycle. Do not change eFuses
    without explicit board-specific review and a recoverability plan.
13. Add a firmware protocol version field and a single schema/contract source
    so host requirements, firmware output, and mock fixtures remain aligned.
14. Record exact tool versions, build IDs, image hashes, partition-table hash,
    and effective flash mode/frequency in every hardware report.

## 12. Inventory limitations

- `.pio` was enumerated and summarized, not read file-by-file as authored
  source; most of its contents are generated compiler/build-system products.
- `tests.zip` was listed without extraction. `tests.7z` was identified by its
  archive signature but not decoded because a 7-Zip reader was unavailable.
- No connected-board operation, destructive flash operation, source edit, or
  test run was performed for this inventory.
- Timestamped reports are historical and may have clock/time-zone anomalies;
  their embedded `generated_at` values are the preferred time field.
