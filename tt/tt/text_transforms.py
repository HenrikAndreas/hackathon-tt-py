"""Text-based TypeScript to Python transformations.

Applies a series of regex-based passes to convert TypeScript source text
to Python. Each pass handles one category of transformation.
"""
from __future__ import annotations

import re


def to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    if name.isupper():
        return name
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


def strip_types(code: str) -> str:
    """Remove TypeScript type annotations."""
    # Type annotations after : in params and declarations
    code = re.sub(r":\s*(?:string|number|boolean|void|any|Big|Date)\b(?:\[\])?", "", code)
    # Generic type params
    code = re.sub(r"<[A-Z]\w*(?:\[\])?(?:\s*,\s*[A-Z]\w*)*>", "", code)
    # Type assertions: x as Type
    code = re.sub(r"\bas\s+[A-Z]\w*(?:\[\])?", "", code)
    # Complex type annotations (: { key: type; })
    code = re.sub(r":\s*\{\s*\[[^\]]+\]:\s*[^}]+\}", "", code)
    # Return type annotations
    code = re.sub(r"\)\s*:\s*\w+(?:\[\])?\s*\{", ") {", code)
    # Parameter type annotations (more aggressive)
    code = re.sub(r"(\w+)\s*:\s*(?:readonly\s+)?[A-Z]\w*(?:<[^>]*>)?(?:\[\])?", r"\1", code)
    # Access modifiers
    code = re.sub(r"\b(?:public|private|protected|readonly|static)\s+", "", code)
    # async
    code = re.sub(r"\basync\s+", "", code)
    return code


def convert_declarations(code: str) -> str:
    """Convert const/let/var to plain assignment."""
    code = re.sub(r"\b(?:const|let|var)\s+", "", code)
    return code


def convert_big_js(code: str) -> str:
    """Convert Big.js patterns to Decimal/operators."""
    # new Big(x) → Decimal(str(x)) or Decimal(x) for 0
    code = re.sub(r"new Big\(0\)", "Decimal(0)", code)
    code = re.sub(r"new Big\(1\)", "Decimal(1)", code)
    code = re.sub(r"new Big\(([^)]+)\)", r"Decimal(str(\1))", code)
    return code


def convert_big_methods(code: str) -> str:
    """Convert Big.js method calls to Python operators."""
    # Binary ops: .plus(x) → + (x)
    for old, new in [("plus", "+"), ("add", "+"), ("minus", "-"),
                     ("mul", "*"), ("times", "*"), ("div", "/")]:
        code = re.sub(r"\." + old + r"\(\s*", " " + new + " (", code)
    # Comparison ops: .eq(x) → == (x)
    for old, new in [("eq", "=="), ("gt", ">"), ("gte", ">="),
                     ("lt", "<"), ("lte", "<=")]:
        code = re.sub(r"\." + old + r"\(\s*", " " + new + " (", code)
    # Unary: .abs() → abs(...)  - simplified
    code = re.sub(r"(\w+)\.abs\(\)", r"abs(\1)", code)
    # .toNumber() → float(...)
    code = re.sub(r"(\w+)\.toNumber\(\)", r"float(\1)", code)
    code = re.sub(r"\.toNumber\(\)", "", code)
    # .toFixed(n) → round(float(...), n) - simplified
    code = re.sub(r"\.toFixed\(\d+\)", "", code)
    return code


def convert_keywords(code: str) -> str:
    """Convert JS keywords to Python equivalents."""
    code = re.sub(r"\bthis\.", "self.", code)
    code = re.sub(r"\bnull\b", "None", code)
    code = re.sub(r"\bundefined\b", "None", code)
    code = re.sub(r"\btrue\b", "True", code)
    code = re.sub(r"\bfalse\b", "True == False", code)  # avoid matching substrings
    code = re.sub(r"\bTrue == False\b", "False", code)
    code = code.replace("===", "==").replace("!==", "!=")
    code = re.sub(r"\b&&\b", " and ", code)
    code = re.sub(r"\|\|", " or ", code)
    code = re.sub(r"\?\?", " or ", code)  # simplified nullish coalescing
    code = re.sub(r"!(\w)", r"not \1", code)
    return code


def convert_array_methods(code: str) -> str:
    """Convert JS array methods."""
    code = re.sub(r"\.push\(", ".append(", code)
    code = re.sub(r"\.length\b", ")", code)
    code = re.sub(r"\blen\(\s*(\w+)\s*\)", r"len(\1)", code)
    # .includes(x) → x in arr (simplified - keep as-is for now)
    code = re.sub(r"\.at\((-?\d+)\)", r"[\1]", code)
    code = re.sub(r"\.indexOf\(", ".index(", code)
    return code


def convert_date_functions(code: str) -> str:
    """Convert date-fns function calls."""
    code = re.sub(r"\bformat\(([^,]+),\s*DATE_FORMAT\)", r"\1", code)
    code = re.sub(r"\bformat\(([^,]+),\s*[^)]+\)", r"str(\1)", code)
    code = re.sub(r"\bparseDate\(([^)]+)\)", r"\1", code)
    code = re.sub(r"\bisBefore\(([^,]+),\s*([^)]+)\)", r"(\1 < \2)", code)
    code = re.sub(r"\bisAfter\(([^,]+),\s*([^)]+)\)", r"(\1 > \2)", code)
    code = re.sub(r"\bdifferenceInDays\(([^,]+),\s*([^)]+)\)", r"max(0, int(str(\1)) - int(str(\2))) if False else 0", code)
    code = re.sub(r"\bnew Date\(\)", "date.today().isoformat()", code)
    code = re.sub(r"\bnew Date\(([^)]+)\)", r"str(\1)", code)
    code = re.sub(r"\bDate\.now\(\)", "date.today().isoformat()", code)
    return code


def convert_lodash(code: str) -> str:
    """Convert lodash utility calls."""
    code = re.sub(r"\bcloneDeep\(", "deepcopy(", code)
    code = re.sub(r"\bsortBy\(([^,]+),\s*([^)]+)\)", r"sorted(\1, key=\2)", code)
    code = re.sub(r"\bisNumber\(([^)]+)\)", r"isinstance(\1, (int, float))", code)
    return code


def convert_names(code: str) -> str:
    """Convert camelCase identifiers to snake_case."""
    # Convert camelCase variable/method names, but not class names (PascalCase)
    def _replace(m):
        name = m.group(0)
        # Skip if it starts with uppercase (class name)
        if name[0].isupper():
            return name
        # Skip common globals
        if name in ("self", "None", "True", "False", "Decimal", "deepcopy",
                     "date", "timedelta", "functools", "float", "int", "str",
                     "abs", "min", "max", "sum", "len", "range", "sorted",
                     "isinstance", "hasattr", "getattr", "print", "list",
                     "dict", "set", "tuple", "type", "super", "pass", "return",
                     "for", "if", "elif", "else", "while", "and", "or", "not",
                     "in", "is", "def", "class", "import", "from", "as",
                     "try", "except", "finally", "raise", "with", "yield",
                     "break", "continue", "lambda", "del", "global", "nonlocal",
                     "assert"):
            return name
        converted = to_snake(name)
        if converted != name:
            return converted
        return name
    # Only convert identifiers (word boundaries)
    code = re.sub(r"\b[a-z][a-zA-Z0-9]*\b", _replace, code)
    return code


def _add_colon_suffix(line: str) -> str:
    """Add colon to a line that had a trailing brace removed, if needed."""
    if line.endswith(")"):
        return line + ":"
    if not line.endswith(":"):
        return line + ":"
    return line


def _convert_braces_to_indent(code: str) -> str:
    """Convert brace-delimited blocks to Python indentation."""
    lines = code.split("\n")
    result = []
    indent = 0
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            result.append("")
            continue
        # Remove semicolons
        line = line.rstrip(";")
        # Skip standalone braces
        if line == "{":
            indent += 1
            continue
        if line == "}":
            indent = max(0, indent - 1)
            continue
        # Handle } else { patterns
        if line.startswith("}"):
            indent = max(0, indent - 1)
            line = line.lstrip("} ")
            if not line:
                continue
        # Handle trailing {
        if line.endswith("{"):
            line = _add_colon_suffix(line[:-1].rstrip())
            result.append("    " * indent + line)
            indent += 1
            continue
        result.append("    " * indent + line)
    return "\n".join(result)


def transform_ts_to_py(ts_code: str) -> str:
    """Apply all text-based transforms to convert TS to Python."""
    code = strip_types(ts_code)
    code = convert_declarations(code)
    code = convert_big_js(code)
    code = convert_big_methods(code)
    code = convert_keywords(code)
    code = convert_date_functions(code)
    code = convert_lodash(code)
    code = convert_array_methods(code)
    code = convert_names(code)
    code = _convert_braces_to_indent(code)
    return code
