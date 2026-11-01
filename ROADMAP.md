# Roadmap

This roadmap lists candidate improvements, not completed features. Priorities
may change based on hardware feedback and maintainer availability.

## Near term

- Add a GitHub Actions workflow for supported Python versions, host regression
  tests, and basic static checks.
- Pin or document tested PlatformIO platform, Arduino framework, ESP-IDF, and
  esptool versions to improve reproducibility.
- Add sanitized, small report fixtures and tests for report compatibility.
- Improve configuration for LED pin, Wi-Fi expectations, and board profiles
  without weakening safe behavior for ambiguous serial devices.

## Medium term

- Expand hardware-in-loop validation to multiple ESP32 variants and USB-UART
  bridges, recording the test matrix and known limitations.
- Add optional external GPIO/LED feedback so the test can validate an
  electrical response rather than only software toggling.
- Improve Wi-Fi diagnostics for environments where zero visible APs is
  expected, while keeping the result explicit.
- Add clearer NVS test isolation and safeguards against collisions with
  application data.
- Review report retention, privacy, and redaction behavior.

## Longer term

- Define versioned board profiles and machine-readable test result schemas.
- Add repeatability/soak testing and trend comparison across runs.
- Document secure production provisioning separately from this diagnostic
  framework and avoid handling production secrets in host tooling.
