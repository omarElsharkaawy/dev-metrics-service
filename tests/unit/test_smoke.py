import devmetrics


def test_package_exposes_version() -> None:
    assert devmetrics.__version__ == "0.1.0"
