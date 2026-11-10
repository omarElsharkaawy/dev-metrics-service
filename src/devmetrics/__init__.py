"""devmetrics: engineering metrics service."""

from importlib.metadata import version

__version__ = version("devmetrics")


def main() -> None:
    print(f"devmetrics {__version__}")
