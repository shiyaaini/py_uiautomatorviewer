import os
import re
from typing import Dict, List, Any

class DocParser:
    def __init__(self, doc_path: str):
        self.doc_path = doc_path
        self.api_data = {}

    def parse_all(self):
        if not os.path.exists(self.doc_path):
            print(f"Warning: Doc path {self.doc_path} does not exist")
            return {}

        for filename in os.listdir(self.doc_path):
            if filename.endswith(".md"):
                self._parse_file(os.path.join(self.doc_path, filename))
        
        return self.api_data

    def _parse_file(self, file_path: str):
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        module_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Special case handling for module names if needed
        # e.g., 'app.md' -> 'app'
        
        current_item = None
        
        for line in lines:
            line = line.strip()
            
            # Match headers like "## app.versionCode" or "## files.read(path)"
            # Regex to capture: ## (module.name|name)(args)?
            match_dot = re.match(r"^##\s+([a-zA-Z0-9_]+\.[a-zA-Z0-9_.]+)(\(.*\))?", line)
            
            # Match headers like "## [m] show" (common in AutoJs6 docs)
            match_bracket = re.match(r"^##\s+\[[a-zA-Z]\]\s+([a-zA-Z0-9_]+)", line)
            
            if match_dot:
                full_name = match_dot.group(1)
                args = match_dot.group(2) or ""
                
                parts = full_name.split('.')
                
                if len(parts) >= 2:
                    mod = parts[0]
                    name = parts[1]
                    self._add_item(mod, name, args)
                    current_item = self.api_data[mod]["children"][name]
                    
            elif match_bracket:
                name = match_bracket.group(1)
                # Use filename as module name (e.g. console.md -> console)
                mod = module_name
                self._add_item(mod, name, "")
                current_item = self.api_data[mod]["children"][name]
                
            elif current_item and line and not line.startswith("#") and not line.startswith("*"):
                # Simple doc extraction
                if not current_item["doc"]:
                    current_item["doc"] = line.strip()
                # Try to extract args from "### method(args)" if we missed them
                if not current_item["args"] and line.startswith("###"):
                     match_args = re.match(r"^###\s+" + re.escape(current_item.get("name", "")) + r"(\(.*\))", line)
                     # Actually the name might be in the line
                     match_args_generic = re.match(r"^###\s+.*\((.*)\)", line)
                     if match_args_generic:
                         current_item["args"] = "(" + match_args_generic.group(1) + ")"

    def _add_item(self, mod: str, name: str, args: str):
        if mod not in self.api_data:
            self.api_data[mod] = {"type": "module", "children": {}}
        
        self.api_data[mod]["children"][name] = {
            "type": "function" if args else "property",
            "args": args,
            "doc": "",
            "name": name
        }

