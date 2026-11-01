"""Classify ESP32 boot/reset output and provide diagnostic next steps."""

from __future__ import annotations

import re
from typing import Any


_ISSUE_DEFINITIONS: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "INVALID_HEADER",
        "HIGH",
        r"\binvalid\s+header\b|\binvalid\s+image\b|"
        r"\bimage\s+at\s+0x[0-9a-f]+\s+has\s+invalid\b|"
        r"\bboot:\s*0x(?:0|ff)\b",
        (
            "Corrupt or incompatible firmware image, or an incorrect boot partition/flash offset.",
            "Flash read instability caused by power, wiring, or flash hardware.",
        ),
        (
            "Reflash a known-good image for the exact ESP32 variant and verify its partition table and flash offset.",
            "Check supply stability, flash wiring, and flash ID/status diagnostics.",
        ),
    ),
    (
        "FLASH_READ_ERROR",
        "HIGH",
        r"\bflash\s+read\s+err(?:or)?\b",
        (
            "Unreliable flash communication, damaged flash, or unstable supply.",
            "Incorrect flash configuration or incompatible image.",
        ),
        (
            "Check power integrity and flash hardware; retry with a known-good cable and board.",
            "Verify flash ID/status and rebuild for the selected chip and flash configuration.",
        ),
    ),
    (
        "BROWNOUT_RESET",
        "HIGH",
        r"\bBROWNOUT_RESET\b|\bbrownout\s+detector\b",
        (
            "Supply voltage dipped below the brownout threshold during startup or load.",
            "USB cable, regulator, or peripheral load is inadequate.",
        ),
        (
            "Use a stable supply with adequate current and inspect cable/regulator voltage under load.",
            "Disconnect peripherals and repeat the boot test.",
        ),
    ),
    (
        "RTC_WATCHDOG_RESET",
        "HIGH",
        r"\bRTCWDT_RTC_RESET\b",
        (
            "RTC watchdog expired during early boot or reset recovery.",
            "Repeated brownout, unstable reset/strapping pins, or boot-time hardware/flash failure.",
        ),
        (
            "Capture repeated reset cycles and correlate them with power-on and brownout messages.",
            "Check supply, EN/BOOT strapping, flash diagnostics, and the flashed image.",
        ),
    ),
    (
        "TG0_WATCHDOG_RESET",
        "HIGH",
        r"\bTG0WDT_SYS_RESET\b",
        (
            "Timer Group 0 watchdog reset the system.",
            "Boot/task code stalled, watchdog servicing was blocked, or a startup dependency hung.",
        ),
        (
            "Inspect the preceding task/boot log and identify code that blocks without yielding.",
            "Check watchdog configuration and repeat with a minimal known-good firmware.",
        ),
    ),
    (
        "TG1_WATCHDOG_RESET",
        "HIGH",
        r"\bTG1WDT_SYS_RESET\b",
        (
            "Timer Group 1 watchdog reset the system.",
            "A task or startup path stalled, or watchdog servicing was blocked.",
        ),
        (
            "Inspect the preceding task/boot log for blocking operations and watchdog timeouts.",
            "Check watchdog configuration and repeat with a minimal known-good firmware.",
        ),
    ),
    (
        "WATCHDOG_RESET",
        "HIGH",
        r"\btask\s+watchdog\b|\bwatchdog\s+reset\b|\bwdt\s+reset\b|\brst\s+cause\s*:\s*4\b",
        (
            "A watchdog timeout or generic watchdog reset indication was reported.",
            "A blocked task, startup stall, or watchdog-servicing issue may have triggered it.",
        ),
        (
            "Inspect the log immediately before the reset and identify blocking code paths.",
            "Check watchdog configuration and retry with a minimal known-good firmware.",
        ),
    ),
    (
        "POWER_ON_RESET",
        "INFO",
        r"\bPOWERON_RESET\b",
        ("A power-on reset was reported; this is normally an expected cold boot.",),
        ("No corrective action is required unless it repeats unexpectedly.",),
    ),
    (
        "SOFTWARE_RESET",
        "LOW",
        r"\bSW_RESET\b",
        ("Firmware or a software-controlled reset initiated the reboot.",),
        ("Inspect application reset calls and the log immediately preceding the reset.",),
    ),
    (
        "GURU_MEDITATION",
        "CRITICAL",
        r"\bGuru\s+Meditation\b",
        (
            "Firmware encountered an exception, invalid memory access, or assertion failure.",
            "A stack trace may identify the faulting function and source location.",
        ),
        (
            "Decode the backtrace against the exact firmware ELF and inspect the exception registers.",
            "Check pointer lifetimes, stack usage, task concurrency, and recent code changes.",
        ),
    ),
    (
        "PANIC_OR_ABORT",
        "CRITICAL",
        r"\bpanic(?:ed)?\b|\babort\(\)",
        ("Firmware panic, assertion, or explicit abort stopped normal execution.",),
        (
            "Preserve and decode the panic backtrace using the matching firmware ELF.",
            "Review the assertion or abort location and the state that triggered it.",
        ),
    ),
)

_RESET_PRIORITY = {
    "CRITICAL": 0,
    "HIGH": 1,
    "LOW": 2,
    "INFO": 3,
}


def analyze_bootlog(text: str) -> dict[str, Any]:
    """Return a backward-compatible classification plus actionable issues."""
    issues: list[dict[str, Any]] = []
    lines = text.splitlines()

    for code, severity, expression, causes, actions in _ISSUE_DEFINITIONS:
        if code == "WATCHDOG_RESET" and any(
            issue["code"]
            in {"RTC_WATCHDOG_RESET", "TG0_WATCHDOG_RESET", "TG1_WATCHDOG_RESET"}
            for issue in issues
        ):
            continue
        pattern = re.compile(expression, re.IGNORECASE)
        matching_lines = [line.strip() for line in lines if pattern.search(line)]
        if matching_lines:
            issues.append(
                {
                    "code": code,
                    "severity": severity,
                    "likely_causes": list(causes),
                    "recommended_actions": list(actions),
                    "matching_lines": matching_lines,
                }
            )

    reset_reason_patterns = (
        ("RTCWDT_RTC_RESET", "RTC_WATCHDOG_RESET"),
        ("TG0WDT_SYS_RESET", "TG0_WATCHDOG_RESET"),
        ("TG1WDT_SYS_RESET", "TG1_WATCHDOG_RESET"),
        ("BROWNOUT_RESET", "BROWNOUT_RESET"),
        ("POWERON_RESET", "POWER_ON_RESET"),
        ("SW_RESET", "SOFTWARE_RESET"),
    )
    existing_codes = {issue["code"] for issue in issues}
    for reason, issue_code in reset_reason_patterns:
        if reason == "BROWNOUT_RESET":
            continue
        matching_lines = [
            line.strip()
            for line in lines
            if re.search(rf"\b{re.escape(reason)}\b", line, re.IGNORECASE)
        ]
        if matching_lines and issue_code not in existing_codes:
            definition = next(
                item for item in _ISSUE_DEFINITIONS if item[0] == issue_code
            )
            issues.append(
                {
                    "code": issue_code,
                    "severity": definition[1],
                    "likely_causes": list(definition[3]),
                    "recommended_actions": list(definition[4]),
                    "matching_lines": matching_lines,
                }
            )

    invalid_flash_ids = [
        line.strip()
        for line in lines
        if re.search(r"\bManufacturer\s*:\s*(?:0x)?ff\b", line, re.IGNORECASE)
        or re.search(r"\bDevice\s*:\s*(?:0x)?ffff\b", line, re.IGNORECASE)
    ]
    if invalid_flash_ids:
        issues.append(
            {
                "code": "INVALID_FLASH_ID",
                "severity": "HIGH",
                "likely_causes": [
                    "Flash identification returned erased/all-ones values.",
                    "Flash communication, supply, or hardware may be faulty.",
                ],
                "recommended_actions": [
                    "Repeat chip/flash identification with a stable supply and reliable USB cable.",
                    "Inspect the board and flash configuration; compare results with a known-good unit.",
                ],
                "matching_lines": invalid_flash_ids,
            }
        )

    matching_lines = [line for issue in issues for line in issue["matching_lines"]]
    findings = [
        f"{issue['code']}: {issue['likely_causes'][0]}" for issue in issues
    ]
    classification = _classification(issues, text)
    return {
        "classification": classification,
        "findings": findings,
        "matching_lines": matching_lines,
        "issues": issues,
    }


def _classification(issues: list[dict[str, Any]], text: str) -> str:
    if not issues:
        if re.search(r"\bREADY:esp32_test_firmware\b", text):
            return "NORMAL_BOOT"
        return "UNKNOWN" if text.strip() else "EMPTY"

    ranked = sorted(
        issues,
        key=lambda issue: _RESET_PRIORITY.get(issue["severity"], 4),
    )
    selected = ranked[0]["code"]
    classification_names = {
        "INVALID_HEADER": "INVALID_IMAGE",
        "FLASH_READ_ERROR": "FLASH_READ_ERROR",
        "RTC_WATCHDOG_RESET": "RTCWDT_RTC_RESET",
        "TG0_WATCHDOG_RESET": "TG0WDT_SYS_RESET",
        "TG1_WATCHDOG_RESET": "TG1WDT_SYS_RESET",
        "WATCHDOG_RESET": "WATCHDOG_RESET",
        "POWER_ON_RESET": "POWERON_RESET",
        "SOFTWARE_RESET": "SW_RESET",
        "GURU_MEDITATION": "PANIC",
        "PANIC_OR_ABORT": "PANIC",
    }
    return classification_names.get(selected, selected)


def main() -> int:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Analyze an ESP32 serial boot log.")
    parser.add_argument("log_file", type=Path, help="Path to a captured serial log")
    args = parser.parse_args()
    if not args.log_file.is_file():
        parser.error(f"log file does not exist: {args.log_file}")

    result = analyze_bootlog(args.log_file.read_text(encoding="utf-8", errors="replace"))
    print(json.dumps(result, indent=2))
    return 1 if any(issue["severity"] in {"CRITICAL", "HIGH"} for issue in result["issues"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
