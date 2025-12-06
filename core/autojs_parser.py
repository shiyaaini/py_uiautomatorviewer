import json
from typing import Optional, Tuple
from dataclasses import dataclass

from .uixml_parser import UiNode


class AutoJsTreeParser:
    def parse_json(self, json_path: str) -> Optional[UiNode]:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._parse_node(data, None)
        except Exception as e:
            print(f"JSON parse error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_bounds(self, bounds_str: str) -> Tuple[int, int, int, int]:
        import re
        try:
            matches = re.findall(r"\[(\d+),(\d+)\]", bounds_str)
            if len(matches) == 2:
                x1, y1 = map(int, matches[0])
                x2, y2 = map(int, matches[1])
                return (x1, y1, x2 - x1, y2 - y1)
        except Exception:
            pass
        return (0, 0, 0, 0)

    def _parse_node(self, data: dict, parent: Optional[UiNode]) -> UiNode:
        bounds_str = data.get("bounds") or data.get("bounds_str") or "[0,0][0,0]"
        rect = self._parse_bounds(bounds_str)

        node = UiNode(
            index=int(data.get("index", 0)),
            text=data.get("text", ""),
            resource_id=data.get("resource_id") or data.get("resource-id", ""),
            class_name=data.get("class_name") or data.get("class", ""),
            package=data.get("package", ""),
            content_desc=data.get("content_desc") or data.get("content-desc", ""),
            checkable=str(data.get("checkable", "false")),
            checked=str(data.get("checked", "false")),
            clickable=str(data.get("clickable", "false")),
            enabled=str(data.get("enabled", "false")),
            focusable=str(data.get("focusable", "false")),
            focused=str(data.get("focused", "false")),
            scrollable=str(data.get("scrollable", "false")),
            long_clickable=str(data.get("long_clickable") or data.get("long-clickable", "false")),
            password=str(data.get("password", "false")),
            selected=str(data.get("selected", "false")),
            bounds_str=bounds_str,
            rect=rect,
            parent=parent,
        )

        children_data = data.get("children") or []
        for child_data in children_data:
            child_node = self._parse_node(child_data, node)
            node.children.append(child_node)

        return node
