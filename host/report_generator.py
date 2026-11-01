"""Generate JSON, Markdown, and raw serial reports for ESP32 test runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_report(results: dict[str, Any]) -> dict[str, Any]:
    """Return a timestamped report document from one test-run result."""
    report = dict(results)
    report.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    return report


def write_report(results: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    """Write JSON/Markdown reports and the stable raw serial log path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(results)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stem = f"esp32_test_report_{timestamp}"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    raw_log_path = output_dir / "raw_serial_log.txt"

    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    raw_log_path.write_bytes(report.get("raw_serial_log", "").encode("utf-8"))
    return json_path, markdown_path


def _render_markdown(report: dict[str, Any]) -> str:
    tests = report.get("tests", [])
    board_info = report.get("board_information")
    if not isinstance(board_info, dict):
        board_info = next(
            (
                test.get("data", {})
                for test in tests
                if test.get("name") == "board_info" and isinstance(test.get("data"), dict)
            ),
            {},
        )

    lines = [
        "# ESP32 Automated Validation Report",
        "",
        f"- **Overall status:** {report.get('status', 'UNKNOWN')}",
        f"- **Generated:** {report.get('generated_at', 'unknown')}",
        f"- **Port:** {report.get('port', 'unknown')}",
        f"- **Baud rate:** {report.get('baud', 'unknown')}",
        "",
        "## Board Information",
        "",
    ]
    if board_info:
        for key, value in board_info.items():
            lines.append(f"- **{_label(key)}:** {value}")
    else:
        lines.append("Board information was not received.")

    lines.extend(["", "## Firmware Tests", "", "| Test | Status | Detail |", "|---|---|---|"])
    for test in tests:
        name = _cell(test.get("name", "unnamed"))
        status = _cell(test.get("status", "UNKNOWN"))
        detail = _cell(test.get("detail", ""))
        lines.append(f"| {name} | {status} | {detail} |")
    if not tests:
        lines.append("| No tests reported | UNKNOWN | |")

    lines.extend(["", "## Flash Diagnostics", ""])
    diagnostics = report.get("flash_diagnostics", [])
    if diagnostics:
        lines.extend(["| Diagnostic | Status | Error |", "|---|---|---|"])
        for diagnostic in diagnostics:
            issues = diagnostic.get("issues", [])
            error = ", ".join(issue.get("code", "UNKNOWN") for issue in issues)
            lines.append(
                f"| {_cell(diagnostic.get('name', 'unnamed'))} | "
                f"{_cell(diagnostic.get('status', 'UNKNOWN'))} | {_cell(error)} |"
            )
            output = diagnostic.get("output")
            if output:
                lines.extend(["", f"**{diagnostic.get('name', 'Diagnostic')} output:**", "", "```text", output, "```", ""])
    else:
        lines.append("No flash diagnostics were run.")

    boot_analysis = report.get("boot_analysis", {})
    lines.extend(["", "## Boot Diagnostics", ""])
    lines.append(f"- **Classification:** {boot_analysis.get('classification', 'UNKNOWN')}")
    issues = boot_analysis.get("issues", [])
    for issue in issues:
        lines.append(f"- **{issue.get('severity', 'UNKNOWN')} — {issue.get('code', 'UNKNOWN')}**")
        for cause in issue.get("likely_causes", []):
            lines.append(f"  - Likely cause: {cause}")
        for action in issue.get("recommended_actions", []):
            lines.append(f"  - Recommended action: {action}")
        for matching_line in issue.get("matching_lines", []):
            lines.append(f"  - Log: `{matching_line}`")
    if not issues:
        for finding in boot_analysis.get("findings", []):
            lines.append(f"- {finding}")
        if not boot_analysis.get("findings"):
            lines.append("- No recognized boot issue.")

    raw_boot_log = report.get("raw_serial_log") or "\n".join(report.get("boot_log", []))
    lines.extend(["", "## Raw Boot Log", ""])
    if raw_boot_log:
        lines.extend(["```text", raw_boot_log.rstrip(), "```"])
    else:
        lines.append("No serial output was captured.")

    health = report.get("health", {})
    lines.extend(["", "## Board Health Score", ""])
    if health:
        lines.append(f"- **Score:** {health.get('score', 0)}/100")
        lines.append(f"- **Classification:** {health.get('classification', 'UNKNOWN')}")
        components = health.get("components", {})
        if components:
            lines.extend(["", "| Component | Score |", "|---|---:|"])
            for name, component in components.items():
                lines.append(
                    f"| {_cell(_label(name))} | "
                    f"{component.get('score', 0)}/{component.get('maximum', 0)} |"
                )
    else:
        lines.append("Health score was not calculated.")

    lines.extend(["", "## Classification", ""])
    lines.append(
        str(health.get("classification", "UNKNOWN"))
        if health
        else str(report.get("classification", "UNKNOWN"))
    )
    lines.extend(["", "## Final Verdict", ""])
    lines.append(
        report.get(
            "final_verdict",
            report.get("error", "No final verdict was recorded."),
        )
    )
    return "\n".join(lines) + "\n"


def _label(value: str) -> str:
    return value.replace("_", " ").capitalize()


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")
