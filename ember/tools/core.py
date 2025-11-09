# ember/tools/core.py
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

@dataclass
class Tool:
    name: str
    desc: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    fn: Optional[Callable[[Any, Dict[str, Any]], Any]] = None  # ctx, args

REGISTRY: Dict[str, Tool] = {}

def register_tool(name: str, desc: str, input_schema=None, output_schema=None):
    """
    Decorator to register a Python function as a tool.

    Example:
    @register_tool("ammo_status", "Return ammo counts")
    def ammo_status(ctx, args): ...
    """
    def deco(fn: Callable[[Any, Dict[str, Any]], Any]):
        REGISTRY[name] = Tool(
            name=name,
            desc=desc,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
            fn=fn,
        )
        return fn

    return deco
