import xml.etree.ElementTree as ET
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

@dataclass
class UiNode:
    """表示界面上的一个控件节点"""
    index: int
    text: str
    resource_id: str
    class_name: str
    package: str
    content_desc: str
    checkable: str
    checked: str
    clickable: str
    enabled: str
    focusable: str
    focused: str
    scrollable: str
    long_clickable: str
    password: str
    selected: str
    bounds_str: str
    rect: Tuple[int, int, int, int] = (0, 0, 0, 0) # x, y, w, h
    children: List['UiNode'] = field(default_factory=list)
    parent: Optional['UiNode'] = None

    @property
    def display_text(self) -> str:
        """树节点显示的文本"""
        parts = []
        if self.class_name:
            parts.append(self.class_name.split('.')[-1]) # 简写类名
        if self.text:
            parts.append(f'text="{self.text}"')
        elif self.content_desc:
             parts.append(f'desc="{self.content_desc}"')
        elif self.resource_id:
             parts.append(f'id="{self.resource_id}"')
        
        return f"({self.index}) " + " ".join(parts)

class UiXmlParser:
    def parse_xml(self, xml_path: str) -> Optional[UiNode]:
        """解析 XML 文件返回根节点"""
        try:
            print(f"Parsing XML file: {xml_path}")
            tree = ET.parse(xml_path)
            root_elem = tree.getroot()
            node = self._parse_element(root_elem)
            print(f"XML Parsed successfully. Root bounds: {node.rect}")
            return node
        except Exception as e:
            print(f"XML parse error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_element(self, element: ET.Element, parent: Optional[UiNode] = None) -> UiNode:
        attributes = element.attrib
        
        # 解析 bounds "[0,0][1080,1920]"
        bounds_str = attributes.get('bounds', '[0,0][0,0]')
        rect = self._parse_bounds(bounds_str)

        node = UiNode(
            index=int(attributes.get('index', '0')),
            text=attributes.get('text', ''),
            resource_id=attributes.get('resource-id', ''),
            class_name=attributes.get('class', ''),
            package=attributes.get('package', ''),
            content_desc=attributes.get('content-desc', ''),
            checkable=attributes.get('checkable', 'false'),
            checked=attributes.get('checked', 'false'),
            clickable=attributes.get('clickable', 'false'),
            enabled=attributes.get('enabled', 'false'),
            focusable=attributes.get('focusable', 'false'),
            focused=attributes.get('focused', 'false'),
            scrollable=attributes.get('scrollable', 'false'),
            long_clickable=attributes.get('long-clickable', 'false'),
            password=attributes.get('password', 'false'),
            selected=attributes.get('selected', 'false'),
            bounds_str=bounds_str,
            rect=rect,
            parent=parent
        )

        # 递归处理子节点
        for child_elem in element:
            child_node = self._parse_element(child_elem, parent=node)
            node.children.append(child_node)
            
        return node

    def _parse_bounds(self, bounds_str: str) -> Tuple[int, int, int, int]:
        """解析 [x1,y1][x2,y2] 为 (x, y, w, h)"""
        try:
            matches = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
            if len(matches) == 2:
                x1, y1 = map(int, matches[0])
                x2, y2 = map(int, matches[1])
                return (x1, y1, x2 - x1, y2 - y1)
        except:
            pass
        return (0, 0, 0, 0)
