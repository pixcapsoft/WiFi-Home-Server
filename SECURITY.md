# Security Policy

## Supported Versions

Currently, the master branch is the actively supported branch for security updates.

| Version | Supported          |
| ------- | ------------------ |
| 0.5.x   | :white_check_mark: |
| < 0.5.0 | :x:                |

## Important Security Context

**WiFi Home Server** is designed strictly for **local network (LAN) sharing**. 

By default, when you start the server, it binds to `0.0.0.0` on the specified port (default `8765`), meaning that it is explicitly configured to be reachable by **any device** that is connected to the same local area network as your host machine.

### Security Best Practices

1. **Do Not Host Sensitive Information:** Do not add directories containing passwords, personal keys, private financial records, or sensitive system files (e.g., `C:/Windows`, `/root/`, `/home/user/.ssh/`).
2. **Use on Trusted Networks Only:** Avoid running the WiFi Home Server on public Wi-Fi networks (like coffee shops, airports, or unencrypted networks) where malicious actors might intercept traffic or access your shared files.
3. **No Authentication Layer:** The server intentionally lacks an authentication mechanism (like passwords or tokens) for maximum simplicity. If you require strict access controls, consider setting up a traditional encrypted SFTP or SMB share.

## Reporting a Vulnerability

If you discover a security vulnerability in WiFi Home Server, please do not disclose it publicly by creating a GitHub issue right away. 

Instead, please send an email directly to the project maintainers or use the private vulnerability reporting feature on GitHub.

We will try to review your report within 48-72 hours. Please provide full details:
- A description of the vulnerability and its impact.
- Steps to reproduce the issue.
- Any suggested mitigations.

We appreciate all efforts to make our project more secure!
