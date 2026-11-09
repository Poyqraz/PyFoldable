"""Explicit offline packaging check; requires pyproject build tools preinstalled.

Run separately from ordinary pytest: python tests/packaging/check_six_profile_wheel.py
Build/install in an isolated temporary source copy; no solver calls.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def check(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(
        ".git", "build", "dist", "*.egg-info", "__pycache__", ".pytest_cache"))
    built = subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                            '--no-index', '--wheel-dir', str(tmp_path), str(source)], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    wheel, = tmp_path.glob('pyfoldable-*.whl')
    installed = tmp_path / 'installed'
    install = subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-deps', '--no-index',
                              '--target', str(installed), str(wheel)], capture_output=True, text=True)
    assert install.returncode == 0, install.stdout + install.stderr
    code = """import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil
assert len(PROJECT_AIRFOIL_IDS) == 6 and PROJECT_AIRFOIL_IDS[-1] == 'NACA4412'
assert Path(__import__('pyfoldable').__file__).is_relative_to(Path(sys.argv[1]))
assert len({load_project_airfoil(p).metadata['airfoil_coordinate_sha256'] for p in PROJECT_AIRFOIL_IDS}) == 6
print('installed wheel: six coordinate-bound assets loaded; no solver')
"""
    checked = subprocess.run([sys.executable, '-I', '-c', code, str(installed)], cwd=tmp_path, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    print(checked.stdout.strip())


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='pyfoldable-wheel-') as temporary:
        check(Path(temporary))
