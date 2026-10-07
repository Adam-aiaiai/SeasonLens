from __future__ import annotations

from dataclasses import dataclass, field

from .ports import Extension, Tool


@dataclass
class Registry:
    extensions: dict[str, Extension] = field(default_factory=dict)
    tools: dict[tuple[str, str], Tool] = field(default_factory=dict)

    def register_extension(self, extension: Extension) -> None:
        if extension.extension_id in self.extensions:
            raise ValueError(f"Duplicate extension: {extension.extension_id}")
        self.extensions[extension.extension_id] = extension

    def register_tool(self, extension_id: str, action_type: str, tool: Tool) -> None:
        key = (extension_id, action_type)
        if key in self.tools:
            raise ValueError(f"Duplicate tool binding: {extension_id}/{action_type}")
        self.tools[key] = tool

    def resolve(self, extension_id: str, action_type: str) -> Tool | None:
        return self.tools.get((extension_id, action_type))
