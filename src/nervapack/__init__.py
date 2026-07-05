# NervaPack module
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("nervapack")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
