# Contributing to WiFi Home Server

First off, thank you for considering contributing to **WiFi Home Server**! It's people like you that make open-source software such an incredible community.

By participating in this project, we ask that you maintain a respectful and welcoming environment for everyone.

## Table of Contents

- [How Can I Contribute?](#how-can-i-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
  - [Pull Requests](#pull-requests)
- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)

---

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates.
When you create a bug report, include as many details as possible:
- Your OS and Python version.
- The version of CustomTkinter you are using.
- Steps to reproduce the behavior.
- Expected behavior vs actual behavior.
- Any console errors/tracebacks.

### Suggesting Enhancements

Have a great idea for a new feature? We'd love to hear it!
Submit an issue describing your enhancement. Be sure to include:
- A clear description of the feature request.
- Why this enhancement would be useful to most users.
- Any potential alternatives you've considered.

### Pull Requests

The process is simple:

1. **Fork** the repo and create your branch from `master`.
2. If you've added code that should be tested, add tests!
3. Format your code. (Follow PEP-8 guidelines when applicable)
4. Update the `README.md` if your changes add or modify features.
5. Issue your Pull Request!

When opening a Pull Request, please ensure the title clearly describes the change, and provide a detailed summary of what was accomplished in the description body.

## Development Setup

1. Fork and clone the repository.
   ```bash
   git clone https://github.com/pixcapsoft/WiFi-Home-Server.git
   cd WiFi-Home-Server
   ```
2. Create a virtual environment (optional but recommended).
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
3. Install dependencies.
   ```bash
   pip install customtkinter
   ```
4. Run the application to ensure it works.
   ```bash
   python gui.py
   ```

## Code Style Guidelines

- This project generally follows standard [PEP-8](https://pep8.org/) coding style limitline constraints.
- Try to keep functions well-documented with descriptive docstrings.
- **UI Modifications:** If you are modifying the UI components in `gui.py`, please ensure your changes align with the current Dark Theme aesthetic and blue accent colors defined in the global palette.
- **Server Modifications:** Keep `main.py` fully independent of `gui.py`. The HTTP server should remain capable of running exclusively in CLI mode without any CustomTkinter dependencies.

Thank you for contributing! 🚀
