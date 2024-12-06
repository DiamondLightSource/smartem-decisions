import subprocess
import sys

from smartem_decisions import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "smartem_decisions", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
