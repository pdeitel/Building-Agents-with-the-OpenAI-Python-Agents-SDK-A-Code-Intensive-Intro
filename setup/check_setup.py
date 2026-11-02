"""check_setup.py — verify the course environment.

The setup scripts run this automatically. You can also run it yourself from
the course folder with the course environment activated:

    python setup/check_setup.py

Prints one line per check. Exits with status 1 if a required check fails.
Optional checks (API key, microphone, Google Chrome) only print warnings.
"""

import importlib
import importlib.metadata
import os
import shutil
import sys
from pathlib import Path

OK, WARN, FAIL = '[ OK ]', '[WARN]', '[FAIL]'
failures = 0


def report(status: str, message: str) -> None:
    """Print one check result and count required failures."""
    global failures
    if status == FAIL:
        failures += 1
    print(f'{status} {message}')


def check_python() -> None:
    version = '.'.join(map(str, sys.version_info[:3]))
    # LiteLLM (02-05-09) requires Python below 3.15, so the course needs 3.14.
    if sys.version_info[:2] == (3, 14):
        report(OK, f'Python {version} ({sys.executable})')
    else:
        report(FAIL, f'Python {version} — the course requires Python 3.14 '
                     '(3.15 is not supported yet by LiteLLM)')


def check_package(dist: str, module: str) -> None:
    """Confirm a distribution is installed and its module imports."""
    try:
        version = importlib.metadata.version(dist)
        importlib.import_module(module)
        report(OK, f'{dist} {version}')
    except Exception as exc:  # report any install/import problem
        report(FAIL, f'{dist}: {type(exc).__name__}: {exc}')


def check_graphviz() -> None:
    dot = shutil.which('dot')
    if dot:
        report(OK, f'Graphviz dot found: {dot}')
    else:
        report(FAIL, 'Graphviz "dot" not found on PATH (needed by draw_graph)')


def check_playwright_browser() -> None:
    """Confirm Playwright's Chromium is installed; note whether Chrome is."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            chromium = Path(p.chromium.executable_path)
        if chromium.exists():
            report(OK, 'Playwright Chromium installed')
        else:
            report(FAIL, 'Playwright Chromium missing — run: '
                         'python -m playwright install chromium')
    except Exception as exc:
        report(FAIL, f'Playwright check failed: {exc}')

    chrome_paths = [
        '/Applications/Google Chrome.app',
        Path(os.environ.get('PROGRAMFILES', r'C:\Program Files'))
            / 'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)'))
            / 'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('LOCALAPPDATA', ''))
            / 'Google/Chrome/Application/chrome.exe',
    ]
    if any(Path(p).exists() for p in chrome_paths) or shutil.which('google-chrome'):
        report(OK, 'Google Chrome found (02-05-07 uses it by default)')
    else:
        report(WARN, 'Google Chrome not found — in 02-05-07 set '
                     'BROWSER_CHANNEL = None to use Playwright Chromium')


def check_audio() -> None:
    """GPT-Live demo (02-05-10) needs a microphone and an output device."""
    try:
        import sounddevice as sd

        sd.query_devices(kind='input')
        sd.query_devices(kind='output')
        report(OK, 'Microphone and speaker devices available (02-05-10)')
    except Exception as exc:
        report(WARN, f'Audio devices not available for 02-05-10: {exc}')


def check_api_key() -> None:
    if os.environ.get('OPENAI_API_KEY'):
        report(OK, 'OPENAI_API_KEY is set')
    else:
        report(WARN, 'OPENAI_API_KEY is not set in this terminal — see '
                     'README.md, then open a new terminal')


def main() -> None:
    print('=== Checking the course environment ===')
    check_python()

    packages = [('openai', 'openai'), ('openai-agents', 'agents'),
                ('websockets', 'websockets'), ('mcp', 'mcp'),
                ('pydantic', 'pydantic'), ('yfinance', 'yfinance'),
                ('playwright', 'playwright'), ('graphviz', 'graphviz'),
                ('litellm', 'litellm'), ('sounddevice', 'sounddevice'),
                ('jupyterlab', 'jupyterlab'), ('ipykernel', 'ipykernel'),
                ('numpy', 'numpy'), ('pandas', 'pandas')]

    for dist, module in packages:
        check_package(dist, module)

    check_graphviz()
    check_playwright_browser()
    check_audio()

    check_api_key()

    print()
    if failures:
        print(f'{failures} required check(s) failed. Fix them before class.')
        sys.exit(1)
    print('All required checks passed.')


if __name__ == '__main__':
    main()
