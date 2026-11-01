"""Discover, validate, and diagnose ESP32 boards over USB serial."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from bootlog_analyzer import analyze_bootlog
from report_generator import write_report


READY_MESSAGE = "READY:esp32_test_firmware"
RESULT_PREFIX = "TEST_RESULT:"
SUMMARY_PREFIX = "TEST_SUMMARY:"
REQUIRED_TEST_NAMES = frozenset(
    {"serial", "free_heap", "chip_info", "board_info", "wifi_scan", "nvs", "gpio"}
)

_FLASH_FAILURE_PATTERNS = (
    ("FAILED_TO_CONNECT", r"failed to connect"),
    ("NO_SERIAL_DATA", r"no serial data received"),
    ("ESPTOOL_FATAL", r"a fatal error occurred"),
    ("INVALID_PACKET_HEADER", r"invalid head of packet"),
    ("FLASH_READ_ERROR", r"flash read err(?:or)?"),
    ("INVALID_FLASH_MANUFACTURER", r"\bmanufacturer\s*:\s*(?:0x)?ff\b"),
    ("INVALID_FLASH_DEVICE", r"\bdevice\s*:\s*(?:0x)?ffff\b"),
    ("INVALID_IMAGE_HEADER", r"\binvalid header\b"),
)

_FLASH_ISSUE_CAUSES = {
    "FAILED_TO_CONNECT": (
        "The board did not enter the ROM bootloader or the selected port is busy.",
        "USB auto-reset wiring, cable, driver, or serial-port selection is unreliable.",
    ),
    "NO_SERIAL_DATA": (
        "No ROM bootloader response was received.",
        "The board may not be in download mode, or the cable/driver/port is faulty.",
    ),
    "ESPTOOL_FATAL": ("esptool reported a fatal operation or configuration error.",),
    "INVALID_PACKET_HEADER": (
        "Serial data was corrupted or the target was not speaking the expected bootloader protocol.",
    ),
    "FLASH_READ_ERROR": (
        "The flash could not be read reliably.",
        "Supply instability, flash wiring, or flash hardware may be faulty.",
    ),
    "INVALID_FLASH_MANUFACTURER": (
        "Flash identification returned an erased/all-ones manufacturer value.",
        "Flash communication or hardware may be faulty.",
    ),
    "INVALID_FLASH_DEVICE": (
        "Flash identification returned an erased/all-ones device value.",
        "Flash communication or hardware may be faulty.",
    ),
    "INVALID_IMAGE_HEADER": (
        "The image header at the selected flash address was not recognized.",
        "Firmware, partition offset, or flash contents may be incorrect.",
    ),
    "COMMAND_FAILED": ("esptool returned a non-zero exit status.",),
}

_FLASH_ISSUE_ACTIONS = {
    "FAILED_TO_CONNECT": (
        "Close other serial applications; verify the selected port and USB driver.",
        "Retry while holding BOOT, then release it after reset if auto-reset is unavailable.",
    ),
    "NO_SERIAL_DATA": (
        "Check the USB cable/driver and retry in ROM download mode.",
        "Verify board power and port selection.",
    ),
    "ESPTOOL_FATAL": (
        "Review the complete esptool output and check the esptool/target version.",
    ),
    "INVALID_PACKET_HEADER": (
        "Use a reliable data-capable USB cable and retry with no competing serial client.",
        "Ensure the board entered ROM download mode.",
    ),
    "FLASH_READ_ERROR": (
        "Check board supply and flash hardware; retry with a known-good cable.",
        "Compare flash ID/status with a known-good board.",
    ),
    "INVALID_FLASH_MANUFACTURER": (
        "Repeat flash identification with stable power and inspect the flash connection.",
    ),
    "INVALID_FLASH_DEVICE": (
        "Repeat flash identification with stable power and inspect the flash connection.",
    ),
    "INVALID_IMAGE_HEADER": (
        "Check the application image and partition offset; reflash a known-good image if needed.",
    ),
    "COMMAND_FAILED": ("Review the captured output and confirm the command is supported by this chip.",),
}


class SerialRunError(RuntimeError):
    """A serial test failure with the output received before it occurred."""

    def __init__(
        self,
        message: str,
        captured_lines: list[str],
        raw_serial_log: str,
    ) -> None:
        super().__init__(message)
        self.captured_lines = captured_lines
        self.raw_serial_log = raw_serial_log


def detect_esp32_ports() -> list[dict[str, Any]]:
    """Return likely ESP32 USB serial ports, including bridge/device details."""
    try:
        from serial.tools import list_ports
    except ImportError as error:
        raise RuntimeError(
            "pyserial is required for port detection; install dependencies with "
            "`python -m pip install -r requirements.txt`"
        ) from error

    matches: list[dict[str, Any]] = []
    bridge_names = ("cp210", "ch340", "ftdi", "espressif", "silicon labs")
    known_vendors = {0x10C4, 0x1A86, 0x0403, 0x303A}
    for port in list_ports.comports():
        description = port.description or ""
        manufacturer = port.manufacturer or ""
        product = port.product or ""
        identity = " ".join((description, manufacturer, product, port.hwid or ""))
        if any(name in identity.lower() for name in bridge_names) or port.vid in known_vendors:
            matches.append(
                {
                    "device": port.device,
                    "description": description,
                    "manufacturer": manufacturer,
                    "product": product,
                    "vid": port.vid,
                    "pid": port.pid,
                    "hwid": port.hwid or "",
                }
            )
    return matches


def select_serial_port(explicit_port: str | None) -> tuple[str, list[dict[str, Any]]]:
    """Use an explicit port or select the only likely board; reject ambiguity."""
    ports = detect_esp32_ports()
    if explicit_port:
        return explicit_port, ports
    if len(ports) == 1:
        return str(ports[0]["device"]), ports
    if not ports:
        raise RuntimeError(
            "No likely ESP32 USB serial device was detected. Connect the board, "
            "check its USB driver, or specify --port explicitly."
        )
    choices = ", ".join(
        f"{port['device']} ({port['description'] or port['manufacturer'] or 'USB serial'})"
        for port in ports
    )
    raise RuntimeError(
        f"Multiple likely ESP32 serial devices were detected: {choices}. "
        "Specify the board with --port."
    )


def run_serial_tests(
    port: str,
    baud: int = 115200,
    timeout: float = 30.0,
    boot_timeout: float = 15.0,
) -> dict[str, Any]:
    """Connect to a board, trigger its on-device suite, and collect test records."""
    try:
        import serial
    except ImportError as error:
        raise RuntimeError(
            "pyserial is required for hardware tests; install dependencies with "
            "`python -m pip install -r requirements.txt`"
        ) from error

    captured_lines: list[str] = []
    raw_chunks: list[bytes] = []
    tests: list[dict[str, Any]] = []
    summary: dict[str, int] | None = None

    try:
        with serial.Serial(port, baudrate=baud, timeout=0.2) as connection:
            ready_deadline = time.monotonic() + boot_timeout
            while time.monotonic() < ready_deadline:
                line = _read_line(connection, raw_chunks)
                if line:
                    captured_lines.append(line)
                    if READY_MESSAGE in line:
                        break
            else:
                raise TimeoutError(
                    f"firmware did not announce readiness within {boot_timeout:g}s"
                )

            connection.write(b"RUN_TESTS\n")
            connection.flush()
            test_deadline = time.monotonic() + timeout
            while time.monotonic() < test_deadline:
                line = _read_line(connection, raw_chunks)
                if not line:
                    continue
                captured_lines.append(line)
                if line.startswith(RESULT_PREFIX):
                    record = _parse_json_record(line, RESULT_PREFIX)
                    if not all(
                        isinstance(record.get(key), str)
                        for key in ("name", "status", "detail")
                    ):
                        raise RuntimeError(f"test result has invalid fields: {line!r}")
                    if record["status"] not in {"PASS", "FAIL"}:
                        raise RuntimeError(f"test result has unknown status: {line!r}")
                    if not isinstance(record.get("data", {}), dict):
                        raise RuntimeError(f"test result data must be an object: {line!r}")
                    tests.append(record)
                elif line.startswith(SUMMARY_PREFIX):
                    summary = _parse_json_record(line, SUMMARY_PREFIX)
                    if not all(
                        isinstance(summary.get(key), int)
                        and not isinstance(summary.get(key), bool)
                        and summary[key] >= 0
                        for key in ("total", "passed", "failed")
                    ):
                        raise RuntimeError(f"test summary has invalid counts: {line!r}")
                    break
            else:
                raise TimeoutError(f"firmware did not finish tests within {timeout:g}s")
    except TimeoutError as error:
        raise SerialRunError(
            str(error), captured_lines, _decode_raw_chunks(raw_chunks)
        ) from error
    except (OSError, ValueError, RuntimeError) as error:
        raise SerialRunError(
            f"serial communication failed on {port}: {error}",
            captured_lines,
            _decode_raw_chunks(raw_chunks),
        ) from error

    raw_serial_log = _decode_raw_chunks(raw_chunks)
    if summary is None:
        raise SerialRunError("firmware test summary was not received", captured_lines, raw_serial_log)
    if summary.get("total") != len(tests):
        raise SerialRunError(
            f"firmware summary reported {summary.get('total')} tests but "
            f"{len(tests)} result records were received",
            captured_lines,
            raw_serial_log,
        )
    if summary.get("passed", 0) + summary.get("failed", 0) != summary.get("total"):
        raise SerialRunError(
            "firmware test summary counts are inconsistent", captured_lines, raw_serial_log
        )
    test_names = [test["name"] for test in tests]
    missing_tests = REQUIRED_TEST_NAMES.difference(test_names)
    if len(test_names) != len(set(test_names)) or missing_tests:
        missing = ", ".join(sorted(missing_tests)) or "duplicate result names"
        raise SerialRunError(
            f"firmware test suite is incomplete: {missing}",
            captured_lines,
            raw_serial_log,
        )
    reported_passes = sum(test["status"] == "PASS" for test in tests)
    reported_failures = sum(test["status"] == "FAIL" for test in tests)
    if (reported_passes, reported_failures) != (
        summary.get("passed"),
        summary.get("failed"),
    ):
        raise SerialRunError(
            "firmware result records do not match test summary counts",
            captured_lines,
            raw_serial_log,
        )

    boot_analysis = analyze_bootlog("\n".join(captured_lines))
    passed = summary.get("failed", 0) == 0 and all(
        test.get("status") == "PASS" for test in tests
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "port": port,
        "baud": baud,
        "tests": tests,
        "summary": summary,
        "boot_analysis": boot_analysis,
        "boot_log": captured_lines,
        "raw_serial_log": raw_serial_log,
    }


def _read_line(connection: Any, raw_chunks: list[bytes] | None = None) -> str:
    raw_line = connection.readline()
    if raw_chunks is not None:
        raw_chunks.append(raw_line)
    return raw_line.decode("utf-8", errors="replace").strip()


def _decode_raw_chunks(raw_chunks: list[bytes]) -> str:
    return b"".join(raw_chunks).decode("utf-8", errors="replace")


def _parse_json_record(line: str, prefix: str) -> dict[str, Any]:
    try:
        value = json.loads(line[len(prefix) :])
    except json.JSONDecodeError as error:
        raise RuntimeError(f"invalid firmware record {line!r}: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"firmware record must be a JSON object: {line!r}")
    return value


def _run_esptool(port: str, baud: int, command: str, timeout: float) -> dict[str, Any]:
    invocation = [
        sys.executable,
        "-m",
        "esptool",
        "--port",
        port,
        "--baud",
        str(baud),
        command,
    ]
    try:
        process = subprocess.run(
            invocation,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        output = "\n".join(part for part in (process.stdout, process.stderr) if part).strip()
        return _build_flash_result(command, invocation, process.returncode, output)
    except subprocess.TimeoutExpired as error:
        output = _timeout_output(error)
        return {
            "name": _flash_test_name(command),
            "status": "ERROR",
            "command": invocation,
            "return_code": None,
            "error_class": "TIMEOUT",
            "output": output,
            "issues": [
                _flash_issue(
                    "COMMAND_TIMEOUT",
                    output or f"esptool {command} timed out after {timeout:g}s",
                )
            ],
        }
    except OSError as error:
        output = str(error)
        return {
            "name": _flash_test_name(command),
            "status": "ERROR",
            "command": invocation,
            "return_code": None,
            "error_class": "EXECUTION_ERROR",
            "output": output,
            "issues": [
                {
                    "code": "EXECUTION_ERROR",
                    "severity": "MEDIUM",
                    "likely_causes": ["The Python interpreter could not start esptool."],
                    "recommended_actions": [
                        "Check the Python environment and install dependencies with python -m pip install -r requirements.txt."
                    ],
                    "matching_lines": [output],
                }
            ],
        }


def _timeout_output(error: subprocess.TimeoutExpired) -> str:
    output = error.stdout or error.stderr or ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def _build_flash_result(
    command: str, invocation: list[str], return_code: int, output: str
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    lower_output = output.lower()
    module_missing = "no module named esptool" in lower_output
    for code, expression in _FLASH_FAILURE_PATTERNS:
        if re.search(expression, output, re.IGNORECASE):
            issues.append(_flash_issue(code, output))
    if return_code != 0 and not issues and not module_missing:
        issues.append(_flash_issue("COMMAND_FAILED", output))

    status = "ERROR" if module_missing else ("FAIL" if issues else "PASS")
    if module_missing:
        issues.append(
            {
                "code": "TOOL_UNAVAILABLE",
                "severity": "MEDIUM",
                "likely_causes": ["The esptool package is not installed in the active Python environment."],
                "recommended_actions": ["Install project dependencies with python -m pip install -r requirements.txt."],
                "matching_lines": output.splitlines(),
            }
        )
    return {
        "name": _flash_test_name(command),
        "status": status,
        "command": invocation,
        "return_code": return_code,
        "error_class": "TOOL_UNAVAILABLE" if module_missing else issues[0]["code"] if issues else None,
        "output": output,
        "issues": issues,
    }


def _flash_test_name(command: str) -> str:
    return {
        "chip-id": "chip_id",
        "flash-id": "flash_id",
        "read-flash-status": "flash_status",
    }.get(command, command.replace("-", "_"))


def _flash_issue(code: str, output: str) -> dict[str, Any]:
    if code == "COMMAND_TIMEOUT":
        causes = ("The board did not respond before the esptool command timed out.",)
        actions = ("Check bootloader mode, serial-port access, and board power; retry with a longer timeout.",)
        severity = "HIGH"
    else:
        causes = _FLASH_ISSUE_CAUSES.get(code, _FLASH_ISSUE_CAUSES["COMMAND_FAILED"])
        actions = _FLASH_ISSUE_ACTIONS.get(code, _FLASH_ISSUE_ACTIONS["COMMAND_FAILED"])
        severity = "HIGH" if code not in {"ESPTOOL_FATAL", "COMMAND_FAILED"} else "MEDIUM"
    expression = next(
        (pattern for issue_code, pattern in _FLASH_FAILURE_PATTERNS if issue_code == code),
        None,
    )
    matching_lines = [
        line.strip()
        for line in output.splitlines()
        if expression is None or re.search(expression, line, re.IGNORECASE)
    ]
    return {
        "code": code,
        "severity": severity,
        "likely_causes": list(causes),
        "recommended_actions": list(actions),
        "matching_lines": matching_lines,
    }


def run_chip_id(port: str, baud: int = 115200, timeout: float = 20.0) -> dict[str, Any]:
    """Run esptool chip identification and retain its output."""
    return _run_esptool(port, baud, "chip-id", timeout)


def run_flash_id(port: str, baud: int = 115200, timeout: float = 20.0) -> dict[str, Any]:
    """Run esptool flash identification and retain its output."""
    return _run_esptool(port, baud, "flash-id", timeout)


def run_flash_status(port: str, baud: int = 115200, timeout: float = 20.0) -> dict[str, Any]:
    """Read flash status through esptool and retain its output."""
    return _run_esptool(port, baud, "read-flash-status", timeout)


def run_flash_diagnostics(port: str, baud: int) -> list[dict[str, Any]]:
    """Run all requested board-side esptool diagnostics."""
    return [
        run_chip_id(port, baud),
        run_flash_id(port, baud),
        run_flash_status(port, baud),
    ]


def score_board_health(
    tests: list[dict[str, Any]],
    flash_diagnostics: list[dict[str, Any]],
    boot_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Compute a transparent 0-100 score and health classification."""
    tests_by_name = {test.get("name"): test for test in tests}
    components: dict[str, dict[str, int]] = {}

    def add_component(name: str, maximum: int, score: int) -> None:
        components[name] = {"score": max(0, min(maximum, score)), "maximum": maximum}

    add_component(
        "board_information",
        15,
        15 if tests_by_name.get("board_info", {}).get("status") == "PASS" else 0,
    )
    add_component("gpio", 10, 10 if tests_by_name.get("gpio", {}).get("status") == "PASS" else 0)
    add_component(
        "wifi",
        15,
        15 if tests_by_name.get("wifi_scan", {}).get("status") == "PASS" else 0,
    )
    add_component("nvs", 15, 15 if tests_by_name.get("nvs", {}).get("status") == "PASS" else 0)

    memory_data = tests_by_name.get("free_heap", {}).get("data", {})
    free_heap = memory_data.get("free_heap_bytes", 0)
    minimum_free_heap = memory_data.get("minimum_free_heap_bytes", 0)
    if free_heap >= 20_000 and minimum_free_heap >= 10_000:
        memory_score = 15
    elif free_heap >= 10_000 and minimum_free_heap > 0:
        memory_score = 8
    else:
        memory_score = 0
    add_component("memory", 15, memory_score)

    flash_score = 5 * sum(item.get("status") == "PASS" for item in flash_diagnostics)
    add_component("flash_diagnostics", 15, flash_score)

    issue_severities = {
        issue.get("severity") for issue in boot_analysis.get("issues", [])
    }
    boot_classification = boot_analysis.get("classification")
    if boot_classification in {"NORMAL_BOOT", "POWERON_RESET", "SW_RESET"} and not (
        issue_severities & {"CRITICAL", "HIGH"}
    ):
        boot_score = 15
    elif boot_classification and boot_classification not in {"UNKNOWN", "EMPTY"} and not (
        issue_severities & {"CRITICAL", "HIGH"}
    ):
        boot_score = 8
    else:
        boot_score = 0
    add_component("boot_diagnostics", 15, boot_score)

    score = sum(component["score"] for component in components.values())
    classification = (
        "HEALTHY" if score >= 80 else "SUSPECT" if score >= 50 else "DEFECTIVE"
    )
    return {
        "score": score,
        "classification": classification,
        "components": components,
    }


def _make_error_report(
    port: str | None,
    baud: int,
    error: str,
    captured_lines: list[str] | None = None,
    raw_serial_log: str = "",
) -> dict[str, Any]:
    boot_log = captured_lines or []
    return {
        "status": "ERROR",
        "port": port or "undetected",
        "baud": baud,
        "tests": [],
        "flash_diagnostics": [],
        "boot_analysis": analyze_bootlog("\n".join(boot_log)),
        "boot_log": boot_log,
        "raw_serial_log": raw_serial_log,
        "error": error,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Serial port override, e.g. COM4")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--timeout", type=float, default=30.0, help="Test timeout in seconds")
    parser.add_argument(
        "--boot-timeout", type=float, default=15.0, help="Wait for firmware readiness"
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "reports",
        help="Directory for JSON, Markdown, and raw serial reports",
    )
    args = parser.parse_args()

    if args.baud <= 0 or args.timeout <= 0 or args.boot_timeout <= 0:
        parser.error("--baud, --timeout, and --boot-timeout must be positive")

    try:
        port, candidates = select_serial_port(args.port)
    except RuntimeError as error:
        result = _make_error_report(None, args.baud, str(error))
        json_path, markdown_path = write_report(result, args.report_dir)
        raw_path = args.report_dir / "raw_serial_log.txt"
        print(f"ERROR: {error}", file=sys.stderr)
        print(f"Reports: {json_path}, {markdown_path}, and {raw_path}", file=sys.stderr)
        return 2

    try:
        result = run_serial_tests(port, args.baud, args.timeout, args.boot_timeout)
    except SerialRunError as error:
        result = _make_error_report(
            port,
            args.baud,
            str(error),
            error.captured_lines,
            error.raw_serial_log,
        )
    except RuntimeError as error:
        result = _make_error_report(port, args.baud, str(error))

    result["port_candidates"] = candidates
    result["flash_diagnostics"] = run_flash_diagnostics(port, args.baud)
    boot_log_text = "\n".join(result.get("boot_log", []))
    diagnostic_output = "\n".join(
        item.get("output", "") for item in result["flash_diagnostics"]
    )
    result["boot_analysis"] = analyze_bootlog(
        "\n".join(part for part in (boot_log_text, diagnostic_output) if part)
    )
    result["health"] = score_board_health(
        result.get("tests", []),
        result["flash_diagnostics"],
        result["boot_analysis"],
    )
    diagnostic_errors = any(
        item["status"] == "ERROR" for item in result["flash_diagnostics"]
    )
    diagnostic_failures = any(
        item["status"] == "FAIL" for item in result["flash_diagnostics"]
    )
    critical_boot_issue = any(
        issue["severity"] in {"CRITICAL", "HIGH"}
        for issue in result["boot_analysis"]["issues"]
    )
    tests_passed = result.get("status") == "PASS"
    unresolved_run_error = bool(result.get("error")) and not critical_boot_issue
    result["status"] = (
        "ERROR"
        if unresolved_run_error or diagnostic_errors
        else "FAIL"
        if not tests_passed or diagnostic_failures or critical_boot_issue
        else "PASS"
    )
    result["final_verdict"] = _final_verdict(result)

    json_path, markdown_path = write_report(result, args.report_dir)
    raw_path = args.report_dir / "raw_serial_log.txt"
    print(f"Test status: {result['status']}")
    for test in result.get("tests", []):
        print(
            f"{test.get('status', 'UNKNOWN'):>4}  {test.get('name', 'unnamed')}: "
            f"{test.get('detail', '')}"
        )
    for diagnostic in result["flash_diagnostics"]:
        print(f"{diagnostic['status']:>5}  {diagnostic['name']}")
    print(
        f"Board health: {result['health']['score']}/100 "
        f"({result['health']['classification']})"
    )
    print(f"Reports: {json_path}, {markdown_path}, and {raw_path}")
    return 0 if result["status"] == "PASS" else 1 if result["status"] == "FAIL" else 2


def _final_verdict(result: dict[str, Any]) -> str:
    if result["status"] == "ERROR":
        return "INCOMPLETE: one or more required diagnostics could not be completed."
    if result["status"] == "FAIL":
        reason = result.get("error")
        suffix = f" Serial run detail: {reason}" if reason else ""
        classification = result.get("boot_analysis", {}).get("classification")
        diagnosis = (
            f" Boot diagnosis: {classification}."
            if classification and classification not in {"UNKNOWN", "EMPTY"}
            else ""
        )
        return (
            "FAIL: one or more firmware tests or boot diagnostics indicate a fault."
            + diagnosis
            + suffix
        )
    return "PASS: firmware tests and available hardware diagnostics completed successfully."


if __name__ == "__main__":
    raise SystemExit(main())
