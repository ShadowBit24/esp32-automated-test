# Contributing

Thanks for helping improve the ESP32 Automated Validation Framework. Focus
changes on reproducible behavior, preserve the serial protocol and existing
flashing/diagnostic workflows, and document hardware-specific assumptions.

## Before opening an issue

- Search existing issues for a matching report.
- Include the ESP32 family/board, USB-UART bridge, operating system, Python
  version, PlatformIO version, and relevant tool versions.
- Provide the smallest relevant error output and steps to reproduce.
- Redact MAC addresses, serial numbers, Wi-Fi names, credentials, and other
  device-identifying or private information from reports and screenshots.
- Never attach eFuse dumps, encryption keys, credentials, or unredacted raw
  serial logs to a public issue.

Use the bug report or feature request template where available.

## Development setup

Use Python 3.10 or newer. From the project root:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

To build the Arduino validation firmware:

```powershell
platformio run
```

The encrypted helper bootloader is a separate ESP-IDF project. Build it only
when working on that documented workflow:

```powershell
platformio run --project-dir firmware\encrypted_bootloader_support -e esp32dev
```

## Change expectations

- Keep changes focused and preserve existing commands, JSON fields, and report
  behavior unless a change is explicitly documented and tested.
- Add or update offline regression tests for host-side behavior.
- For hardware-dependent changes, state the board, setup, expected result, and
  what could not be verified on hardware.
- Update README or relevant technical documentation when behavior or setup
  changes.
- Do not commit generated `.pio` output, Python caches, local hardware reports,
  raw device logs, or secrets.
- Avoid claiming hardware validation from mocked tests alone.

## Pull requests

Describe the problem, implementation, and compatibility impact. Include test
commands and results. For hardware changes, summarize the actual device and
conditions tested; redact identifiers and private log content.
