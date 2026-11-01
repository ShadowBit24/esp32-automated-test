from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

import bootlog_analyzer
import flash_validator
import report_generator
import test_runner


class BootLogAnalyzerTests(unittest.TestCase):
    def test_requested_boot_failures_include_actionable_details(self) -> None:
        log = "\n".join(
            (
                "invalid header: 0x3ffea272",
                "invalid header: 0x5691acba",
                "invalid header: 0xd610e111",
                "rst:0x10 (RTCWDT_RTC_RESET)",
                "rst:0x1 (POWERON_RESET)",
                "rst:0x3 (SW_RESET)",
                "rst:0x7 (TG0WDT_SYS_RESET)",
                "rst:0x8 (TG1WDT_SYS_RESET)",
                "rst:0x9 (BROWNOUT_RESET)",
                "flash read err, 1000",
                "Guru Meditation Error: Core  0 panic'ed",
                "abort() was called",
            )
        )
        result = bootlog_analyzer.analyze_bootlog(log)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertTrue(
            {
                "INVALID_HEADER",
                "RTC_WATCHDOG_RESET",
                "POWER_ON_RESET",
                "SOFTWARE_RESET",
                "TG0_WATCHDOG_RESET",
                "TG1_WATCHDOG_RESET",
                "BROWNOUT_RESET",
                "FLASH_READ_ERROR",
                "GURU_MEDITATION",
                "PANIC_OR_ABORT",
            }.issubset(codes)
        )
        for issue in result["issues"]:
            self.assertIn(issue["severity"], {"CRITICAL", "HIGH", "LOW", "INFO"})
            self.assertTrue(issue["likely_causes"])
            self.assertTrue(issue["recommended_actions"])

    def test_flash_identification_failure_is_reported(self) -> None:
        result = bootlog_analyzer.analyze_bootlog(
            "Manufacturer: ff\nDevice: ffff\n"
        )
        self.assertIn("INVALID_FLASH_ID", {issue["code"] for issue in result["issues"]})

    def test_legacy_invalid_image_and_watchdog_patterns_remain_supported(self) -> None:
        for line in (
            "image at 0x1000 has invalid magic",
            "boot: 0x0",
        ):
            with self.subTest(line=line):
                result = bootlog_analyzer.analyze_bootlog(line)
                self.assertEqual(result["classification"], "INVALID_IMAGE")
        for line in (
            "rst cause: 4",
            "Task watchdog got triggered",
            "wdt reset",
        ):
            with self.subTest(line=line):
                result = bootlog_analyzer.analyze_bootlog(line)
                self.assertIn("WATCHDOG_RESET", {issue["code"] for issue in result["issues"]})

    def test_normal_boot_and_legacy_fields_are_preserved(self) -> None:
        result = bootlog_analyzer.analyze_bootlog("READY:esp32_test_firmware\n")
        self.assertEqual(result["classification"], "NORMAL_BOOT")
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["matching_lines"], [])
        self.assertEqual(result["issues"], [])


class FlashValidatorTests(unittest.TestCase):
    def test_valid_image_and_sha256_are_accepted(self) -> None:
        payload = bytes((1, 2, 3, 4))
        image = bytearray(80)
        image[0:2] = bytes((0xE9, 1))
        image[28:32] = len(payload).to_bytes(4, "little")
        image[32:36] = payload
        checksum = 0xEF
        for byte in payload:
            checksum ^= byte
        image[47] = checksum
        image[48:80] = hashlib.sha256(image[:48]).digest()
        result = flash_validator.validate_image(bytes(image))
        self.assertEqual(result["segments"], 1)
        self.assertTrue(result["sha256_appended"])

    def test_invalid_magic_is_rejected(self) -> None:
        with self.assertRaises(flash_validator.ImageValidationError):
            flash_validator.validate_image(bytes(24))


class RunnerTests(unittest.TestCase):
    def test_serial_protocol_capture_and_report_shape(self) -> None:
        class FakeSerial:
            def __init__(self, *args, **kwargs) -> None:
                test_names = (
                    "serial",
                    "free_heap",
                    "chip_info",
                    "board_info",
                    "wifi_scan",
                    "nvs",
                    "gpio",
                )
                lines = [
                    b"BOOT:firmware=esp32_test_firmware\r\n",
                    b"READY:esp32_test_firmware\r\n",
                ]
                for name in test_names:
                    data = {"chip_model": "ESP32"} if name == "board_info" else {}
                    record = {
                        "name": name,
                        "status": "PASS",
                        "detail": "test passed",
                        "data": data,
                    }
                    lines.append(
                        ("TEST_RESULT:" + json.dumps(record) + "\r\n").encode()
                    )
                lines.append(
                    b'TEST_SUMMARY:{"total":7,"passed":7,"failed":0}\r\n'
                )
                self.lines = iter(lines)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def readline(self):
                return next(self.lines, b"")

            def write(self, data):
                return len(data)

            def flush(self):
                return None

        with patch.dict(sys.modules, {"serial": types.SimpleNamespace(Serial=FakeSerial)}):
            result = test_runner.run_serial_tests(
                "COM_TEST", timeout=1, boot_timeout=1
            )
        self.assertEqual(result["status"], "PASS")
        board_result = next(
            test for test in result["tests"] if test["name"] == "board_info"
        )
        self.assertEqual(board_result["data"]["chip_model"], "ESP32")
        self.assertIn("\r\n", result["raw_serial_log"])
        self.assertEqual(result["boot_analysis"]["classification"], "NORMAL_BOOT")

    def test_flash_diagnostic_output_is_parsed(self) -> None:
        process = types.SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="A fatal error occurred: Failed to connect",
        )
        with patch.object(test_runner.subprocess, "run", return_value=process):
            result = test_runner.run_chip_id("COM_TEST")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn(
            "FAILED_TO_CONNECT", {issue["code"] for issue in result["issues"]}
        )

    def test_all_requested_esptool_failures_are_classified(self) -> None:
        cases = (
            ("Failed to connect", "FAILED_TO_CONNECT"),
            ("No serial data received", "NO_SERIAL_DATA"),
            ("A fatal error occurred", "ESPTOOL_FATAL"),
            ("invalid head of packet", "INVALID_PACKET_HEADER"),
            ("flash read err, 1000", "FLASH_READ_ERROR"),
            ("Manufacturer: ff", "INVALID_FLASH_MANUFACTURER"),
            ("Device: ffff", "INVALID_FLASH_DEVICE"),
            ("invalid header: 0x3ffea272", "INVALID_IMAGE_HEADER"),
        )
        for output, expected_code in cases:
            with self.subTest(output=output):
                result = test_runner._build_flash_result(
                    "flash-id", ["esptool"], 1, output
                )
                self.assertEqual(result["status"], "FAIL")
                self.assertIn(
                    expected_code, {issue["code"] for issue in result["issues"]}
                )

    def test_port_selection_and_ambiguity(self) -> None:
        candidate = {"device": "COM7", "description": "CP210x USB to UART"}
        with patch.object(
            test_runner, "detect_esp32_ports", return_value=[candidate]
        ):
            port, candidates = test_runner.select_serial_port(None)
        self.assertEqual(port, "COM7")
        self.assertEqual(candidates, [candidate])

        with patch.object(
            test_runner,
            "detect_esp32_ports",
            return_value=[candidate, {"device": "COM8", "description": "CH340"}],
        ):
            with self.assertRaisesRegex(RuntimeError, r"Multiple.*--port"):
                test_runner.select_serial_port(None)
            self.assertEqual(test_runner.select_serial_port("COM8")[0], "COM8")

    def test_device_discovery_error_still_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            arguments = ["test_runner.py", "--report-dir", output]
            with (
                patch.object(sys, "argv", arguments),
                patch.object(
                    test_runner,
                    "select_serial_port",
                    side_effect=RuntimeError("no board detected"),
                ),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                exit_code = test_runner.main()
            self.assertEqual(exit_code, 2)
            raw_log = Path(output) / "raw_serial_log.txt"
            self.assertTrue(raw_log.is_file())
            report_path = next(Path(output).glob("esp32_test_report_*.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "ERROR")
            self.assertEqual(report["error"], "no board detected")

    def test_confirmed_boot_failure_is_not_reported_as_incomplete(self) -> None:
        captured_lines = [
            "rst:0x10 (RTCWDT_RTC_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)",
            "invalid header: 0x2e5af586",
        ]
        with tempfile.TemporaryDirectory() as output:
            arguments = ["test_runner.py", "--port", "COM_TEST", "--report-dir", output]
            with (
                patch.object(sys, "argv", arguments),
                patch.object(
                    test_runner,
                    "select_serial_port",
                    return_value=("COM_TEST", []),
                ),
                patch.object(
                    test_runner,
                    "run_serial_tests",
                    side_effect=test_runner.SerialRunError(
                        "firmware did not announce readiness",
                        captured_lines,
                        "\r\n".join(captured_lines),
                    ),
                ),
                patch.object(test_runner, "run_flash_diagnostics", return_value=[]),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                exit_code = test_runner.main()
            report_path = next(Path(output).glob("esp32_test_report_*.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("INVALID_IMAGE", report["final_verdict"])

    def test_health_score_and_report_output(self) -> None:
        tests = [
            {"name": name, "status": "PASS", "data": {}}
            for name in ("board_info", "gpio", "wifi_scan", "nvs")
        ]
        tests.append(
            {
                "name": "free_heap",
                "status": "PASS",
                "data": {
                    "free_heap_bytes": 50_000,
                    "minimum_free_heap_bytes": 20_000,
                },
            }
        )
        diagnostics = [{"name": "chip_id", "status": "PASS"}] * 3
        boot = bootlog_analyzer.analyze_bootlog("READY:esp32_test_firmware\n")
        health = test_runner.score_board_health(tests, diagnostics, boot)
        self.assertEqual(health["score"], 100)
        self.assertEqual(health["classification"], "HEALTHY")

        report = {
            "status": "PASS",
            "port": "COM_TEST",
            "baud": 115200,
            "tests": tests,
            "flash_diagnostics": diagnostics,
            "boot_analysis": boot,
            "boot_log": ["READY:esp32_test_firmware"],
            "raw_serial_log": "READY:esp32_test_firmware\r\n",
            "health": health,
            "final_verdict": "PASS",
        }
        with tempfile.TemporaryDirectory() as output:
            json_path, markdown_path = report_generator.write_report(report, Path(output))
            raw_path = Path(output) / "raw_serial_log.txt"
            self.assertTrue(json_path.is_file())
            markdown = markdown_path.read_text(encoding="utf-8")
            for section in (
                "## Board Information",
                "## Firmware Tests",
                "## Flash Diagnostics",
                "## Boot Diagnostics",
                "## Raw Boot Log",
                "## Board Health Score",
                "## Classification",
                "## Final Verdict",
            ):
                self.assertIn(section, markdown)
            self.assertEqual(
                raw_path.read_bytes(), b"READY:esp32_test_firmware\r\n"
            )


if __name__ == "__main__":
    unittest.main()
