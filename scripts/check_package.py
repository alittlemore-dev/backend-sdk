import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required")
    wheels = list((ROOT / "dist").glob("*.whl"))
    sdists = list((ROOT / "dist").glob("*.tar.gz"))
    assert len(wheels) == len(sdists) == 1, "Expected exactly one wheel and one sdist"
    for artifact in [*wheels, *sdists]:
        with tempfile.TemporaryDirectory(prefix="backend-sdk-package-") as directory:
            temporary = Path(directory)
            environment = temporary / "venv"
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            subprocess.run([uv, "venv", "--python", sys.executable, str(environment)], check=True)
            subprocess.run(
                [uv, "pip", "install", "--python", str(python), "--no-deps", str(artifact)],
                check=True,
            )
            subprocess.run(
                [
                    str(python),
                    "-I",
                    "-c",
                    "from importlib.metadata import metadata; "
                    "from importlib.resources import files; "
                    "import backend_sdk; "
                    "m = metadata('alittlemore-backend-sdk'); "
                    "assert m['Requires-Python'] == '<3.15,>=3.13'; "
                    "assert not m.get_all('Requires-Dist'); "
                    "assert files(backend_sdk).joinpath('py.typed').is_file(); "
                    "print('Installed package OK:', backend_sdk.__file__)",
                ],
                cwd=temporary,
                check=True,
            )


if __name__ == "__main__":
    main()
