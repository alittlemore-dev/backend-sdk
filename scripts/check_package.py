import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL_VARIANTS = {
    None: "import backend_sdk",
    "auth-http": "from backend_sdk.auth.http import AuthApiClient",
    "litestar": "from backend_sdk.integrations.litestar import AuthPlugin",
}


def main() -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required")
    wheels = list((ROOT / "dist").glob("*.whl"))
    sdists = list((ROOT / "dist").glob("*.tar.gz"))
    assert len(wheels) == len(sdists) == 1, "Expected exactly one wheel and one sdist"
    for artifact in [*wheels, *sdists]:
        for extra, integration_import in INSTALL_VARIANTS.items():
            check_artifact(
                artifact=artifact, extra=extra, integration_import=integration_import, uv=uv
            )


def check_artifact(*, artifact: Path, extra: str | None, integration_import: str, uv: str) -> None:
    requirement = str(artifact) if extra is None else f"{artifact}[{extra}]"
    with tempfile.TemporaryDirectory(prefix="backend-sdk-package-") as directory:
        temporary = Path(directory)
        environment = temporary / "venv"
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([uv, "venv", "--python", sys.executable, str(environment)], check=True)
        install_command = [uv, "pip", "install", "--python", str(python)]
        if extra is None:
            install_command.append("--no-deps")
        subprocess.run([*install_command, requirement], check=True)
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                f"{integration_import}; "
                "from importlib.metadata import metadata; "
                "from importlib.resources import files; "
                "import backend_sdk; "
                "m = metadata('alittlemore-backend-sdk'); "
                "assert m['Requires-Python'] == '<3.15,>=3.13'; "
                "assert m.get_all('Provides-Extra') == ['auth-http', 'litestar']; "
                "assert files(backend_sdk).joinpath('py.typed').is_file(); "
                f"print('Installed package OK ({extra or 'base'}):', backend_sdk.__file__)",
            ],
            cwd=temporary,
            check=True,
        )


if __name__ == "__main__":
    main()
