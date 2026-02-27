import json
import re


def parse_diagram_update(text: str) -> dict | None:
    match = re.search(r"<diagram_update>(.*?)</diagram_update>", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None
    return None


def parse_mermaid_diagram(text: str) -> str | None:
    match = re.search(r"<mermaid_diagram>(.*?)</mermaid_diagram>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
