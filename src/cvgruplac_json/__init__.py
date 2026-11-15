"""Link the JSONs of cvlac-json and gruplac-json: one id per product, in both directions."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cvgruplac-json")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0"

__all__ = ["__version__"]
