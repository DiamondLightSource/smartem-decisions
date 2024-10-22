import subprocess
import sys

from cryoem_decision_engine_poc import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "cryoem_decision_engine_poc", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
