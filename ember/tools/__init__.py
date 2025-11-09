# ember/tools/__init__.py
from .core import REGISTRY, Tool, register_tool


def load_all_tools():
    """
    For now this does nothing. In the future, it will:
    - auto-import all modules in this package
    - load external tools from a manifest
    """
    # placeholder so callers don't have to change later
    return REGISTRY
