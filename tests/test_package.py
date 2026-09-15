from importlib.metadata import metadata
from importlib.resources import files

import backend_sdk


def test_package_metadata() -> None:
    package = metadata("alittlemore-backend-sdk")
    assert package["Requires-Python"] == "<3.15,>=3.13"
    assert not package.get_all("Requires-Dist")


def test_typing_marker_is_packaged() -> None:
    assert files(backend_sdk).joinpath("py.typed").is_file()
