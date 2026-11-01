# Security Policy

## Scope and limitations

This project is a diagnostic and validation utility, not a secure-boot
implementation or a production flash-encryption provisioning tool. The
encryption-aware helper requires encryption to already be enabled and does not
program eFuses. The encrypted flashing workflow is device-configuration
specific; an incorrect image, offset, or encryption mode can make a board
unbootable.

Host reports and serial captures can contain MAC addresses, board details,
boot output, and filesystem paths. Review and redact them before sharing.
Never publish credentials, encryption keys, eFuse dumps, or other secrets.

## Reporting a vulnerability

Please do not publish exploit details or sensitive device information in a
public issue. If this repository is hosted on GitHub, use its private Security
Advisory reporting feature. If private reporting is unavailable, contact the
maintainer through a verified private channel before public disclosure. Include
the affected version/commit, impact, prerequisites, and a minimal safe
reproduction.

There is currently no published repository URL or verified security contact
configured in this workspace; do not treat an unverified account or address as
an official reporting channel.
