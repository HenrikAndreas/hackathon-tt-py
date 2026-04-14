"""Transform TypeScript AST nodes to Python source code."""
from __future__ import annotations

import re
from typing import Optional


def to_snake_case(name: str) -> str:
    """Convert camelCase to snake_case, preserving UPPER_CASE and PascalCase class names."""
    if name.isupper() or name.startswith("_") and name[1:].isupper():
        return name
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


# Names that should NOT be snake_cased (class names, constants, type names)
_PRESERVE_CASE = {
    "Big",
    "Decimal",
    "Date",
    "PortfolioCalculator",
    "RoaiPortfolioCalculator",
    "PortfolioOrder",
    "PortfolioOrderItem",
    "SymbolProfile",
    "SymbolMetrics",
    "TransactionPointSymbol",
    "CurrentRateService",
    "PortfolioSnapshot",
    "TimelinePosition",
    "Logger",
    "Number",
    "Math",
    "Array",
    "Object",
    "Set",
    "Map",
    "JSON",
    "EPSILON",
    "DATE_FORMAT",
    "ENABLE_LOGGING",
    "INVESTMENT_ACTIVITY_TYPES",
    "True",
    "False",
    "None",
}

# Big.js method → Python binary operator
_BIG_BINARY_OPS = {
    "plus": "+",
    "add": "+",
    "minus": "-",
    "sub": "-",
    "mul": "*",
    "times": "*",
    "div": "/",
}

_BIG_COMPARE_OPS = {
    "eq": "==",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}

# Big.js unary methods
_BIG_UNARY = {
    "abs": "abs",
    "toNumber": "float",
}


class Emitter:
    """Recursive TypeScript AST to Python emitter."""

    def __init__(self, source: bytes, import_map: dict | None = None):
        self.source = source
        self.import_map = import_map or {}
        self._indent = 0

    def text(self, node) -> str:
        """Get source text for a node."""
        return self.source[node.start_byte : node.end_byte].decode("utf-8")

    def indent(self) -> str:
        return "    " * self._indent

    def emit(self, node) -> str:
        """Dispatch to the appropriate handler for a node type."""
        if node is None:
            return ""
        ntype = node.type.replace("-", "_")
        handler = getattr(self, f"_emit_{ntype}", None)
        if handler:
            return handler(node)
        return self._emit_default(node)

    def emit_body(self, node) -> str:
        """Emit a statement block body with increased indentation."""
        self._indent += 1
        result = self._emit_statements(node)
        self._indent -= 1
        if not result.strip():
            self._indent += 1
            result = self.indent() + "pass\n"
            self._indent -= 1
        return result

    def _emit_statements(self, node) -> str:
        """Emit all statement children of a node."""
        lines = []
        for child in node.children:
            if child.type in ("{", "}", "(", ")", ";", ","):
                continue
            if child.type == "comment":
                continue
            if child.type.startswith("type_") or child.type == "type_alias_declaration":
                continue
            if child.type == "interface_declaration":
                continue
            line = self.emit(child)
            if line and line.strip():
                lines.append(line)
        return "\n".join(lines) + "\n" if lines else ""

    # ------------------------------------------------------------------
    # Top-level / structural
    # ------------------------------------------------------------------

    def _emit_default(self, node) -> str:
        """Fallback: try to emit children, or return raw text."""
        if node.child_count == 0:
            return self.text(node)
        parts = []
        for child in node.children:
            if child.type in ("{", "}", ";"):
                continue
            parts.append(self.emit(child))
        return " ".join(p for p in parts if p.strip())

    def _emit_program(self, node) -> str:
        return self._emit_statements(node)

    def _emit_export_statement(self, node) -> str:
        """Unwrap export: emit the inner declaration."""
        for child in node.children:
            if child.type not in ("export", "default", ";", "comment"):
                return self.emit(child)
        return ""

    def _emit_import_statement(self, node) -> str:
        """Handle imports via import_map. Strip by default."""
        return ""

    # ------------------------------------------------------------------
    # Class
    # ------------------------------------------------------------------

    def _emit_class_declaration(self, node) -> str:
        name = ""
        base = ""
        body = None
        for child in node.children:
            if child.type == "type_identifier":
                name = self.text(child)
            elif child.type == "identifier":
                name = self.text(child)
            elif child.type == "class_heritage":
                for hc in child.children:
                    if hc.type == "extends_clause":
                        for ec in hc.children:
                            if ec.type in ("type_identifier", "identifier"):
                                base = self.text(ec)
            elif child.type == "class_body":
                body = child

        if not base:
            line = f"{self.indent()}class {name}:\n"
        else:
            line = f"{self.indent()}class {name}({base}):\n"

        if body:
            line += self.emit_body(body)
        return line

    def _emit_class_body(self, node) -> str:
        return self._emit_statements(node)

    # ------------------------------------------------------------------
    # Methods and functions
    # ------------------------------------------------------------------

    def _emit_method_definition(self, node) -> str:
        name_node = node.child_by_field_name("name")
        name = self.text(name_node) if name_node else "unknown"
        py_name = to_snake_case(name) if name not in _PRESERVE_CASE else name

        params_node = node.child_by_field_name("parameters")
        params = self._extract_params(params_node) if params_node else []

        body_node = node.child_by_field_name("body")

        is_abstract = any(
            self.text(c) == "abstract" for c in node.children if c.type == "abstract"
        )

        # Check for decorators/modifiers
        is_static = any(
            self.text(c) in ("static",) for c in node.children
        )

        if is_abstract:
            return ""

        param_str = ", ".join(["self"] + params)
        line = f"{self.indent()}def {py_name}({param_str}):\n"

        if body_node:
            line += self.emit_body(body_node)
        else:
            self._indent += 1
            line += self.indent() + "pass\n"
            self._indent -= 1
        return line

    def _emit_public_field_definition(self, node) -> str:
        """Skip class field declarations (they're type annotations)."""
        return ""

    def _emit_abstract_method_signature(self, node) -> str:
        return ""

    def _emit_property_signature(self, node) -> str:
        return ""

    def _extract_params(self, params_node) -> list[str]:
        """Extract parameter names from a formal_parameters node."""
        params = []
        for child in params_node.children:
            if child.type in ("(", ")", ","):
                continue
            if child.type == "required_parameter" or child.type == "optional_parameter":
                name_node = child.child_by_field_name("pattern")
                if name_node is None:
                    # Try first identifier child
                    for c in child.children:
                        if c.type == "identifier":
                            name_node = c
                            break
                        elif c.type == "object_pattern":
                            name_node = c
                            break
                if name_node:
                    if name_node.type == "object_pattern":
                        params.append(self._emit_object_pattern_as_param(name_node))
                    else:
                        name = self.text(name_node)
                        py_name = to_snake_case(name)
                        # Check for default value
                        val_node = child.child_by_field_name("value")
                        if val_node:
                            params.append(f"{py_name}={self.emit_expr(val_node)}")
                        else:
                            params.append(py_name)
            elif child.type == "identifier":
                params.append(to_snake_case(self.text(child)))
        return params

    def _emit_object_pattern_as_param(self, node) -> str:
        """Convert {a, b, c} destructuring param to **kwargs or individual names."""
        names = []
        for child in node.children:
            if child.type == "shorthand_property_identifier_pattern":
                names.append(to_snake_case(self.text(child)))
            elif child.type == "pair_pattern":
                key = child.child_by_field_name("key")
                if key:
                    names.append(to_snake_case(self.text(key)))
        return "kwargs"

    def _emit_arrow_function(self, node) -> str:
        params_node = node.child_by_field_name("parameters")
        body_node = node.child_by_field_name("body")
        if params_node is None:
            # Single param without parens
            param = node.child_by_field_name("parameter")
            if param:
                params = [to_snake_case(self.text(param))]
            else:
                params = []
        else:
            params = self._extract_params(params_node)

        if body_node and body_node.type == "statement_block":
            # Multi-line arrow: emit as regular function body
            param_str = ", ".join(params) if params else ""
            result = f"lambda {param_str}: None"
            return result
        elif body_node:
            # Expression arrow: lambda
            param_str = ", ".join(params) if params else ""
            expr = self.emit_expr(body_node)
            return f"lambda {param_str}: {expr}"
        return "lambda: None"

    def _emit_function_declaration(self, node) -> str:
        name_node = node.child_by_field_name("name")
        name = to_snake_case(self.text(name_node)) if name_node else "anonymous"
        params_node = node.child_by_field_name("parameters")
        params = self._extract_params(params_node) if params_node else []
        body_node = node.child_by_field_name("body")

        param_str = ", ".join(params)
        line = f"{self.indent()}def {name}({param_str}):\n"
        if body_node:
            line += self.emit_body(body_node)
        else:
            self._indent += 1
            line += self.indent() + "pass\n"
            self._indent -= 1
        return line

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _emit_statement_block(self, node) -> str:
        return self._emit_statements(node)

    def _emit_expression_statement(self, node) -> str:
        for child in node.children:
            if child.type == ";":
                continue
            expr = self.emit_expr(child)
            if expr and expr.strip():
                return f"{self.indent()}{expr}\n"
        return ""

    def _emit_return_statement(self, node) -> str:
        for child in node.children:
            if child.type in ("return", ";"):
                continue
            expr = self.emit_expr(child)
            return f"{self.indent()}return {expr}\n"
        return f"{self.indent()}return\n"

    def _emit_if_statement(self, node) -> str:
        cond_node = node.child_by_field_name("condition")
        cons_node = node.child_by_field_name("consequence")
        alt_node = node.child_by_field_name("alternative")

        cond = self.emit_expr(cond_node) if cond_node else "True"
        # Strip outer parens from condition
        cond = cond.strip()
        if cond.startswith("(") and cond.endswith(")"):
            cond = cond[1:-1]

        result = f"{self.indent()}if {cond}:\n"
        if cons_node:
            result += self.emit_body(cons_node)

        if alt_node:
            # alt_node is an else_clause
            for child in alt_node.children:
                if child.type == "if_statement":
                    # else if
                    inner = self._emit_if_statement(child)
                    result += f"{self.indent()}el{inner.lstrip()}"
                    return result
                elif child.type not in ("else",):
                    result += f"{self.indent()}else:\n"
                    result += self.emit_body(child)
                    return result
            result += f"{self.indent()}else:\n"
            self._indent += 1
            result += self.indent() + "pass\n"
            self._indent -= 1

        return result

    def _emit_else_clause(self, node) -> str:
        for child in node.children:
            if child.type == "else":
                continue
            return self.emit(child)
        return ""

    def _emit_for_in_statement(self, node) -> str:
        """for (const x of arr) → for x in arr:"""
        left_node = node.child_by_field_name("left")
        right_node = node.child_by_field_name("right")
        body_node = node.child_by_field_name("body")

        var_name = self._extract_for_var(left_node) if left_node else "_"
        iterable = self.emit_expr(right_node) if right_node else "[]"

        result = f"{self.indent()}for {var_name} in {iterable}:\n"
        if body_node:
            result += self.emit_body(body_node)
        else:
            self._indent += 1
            result += self.indent() + "pass\n"
            self._indent -= 1
        return result

    def _emit_for_statement(self, node) -> str:
        """C-style for loop → while loop or range."""
        init_node = node.child_by_field_name("initializer")
        cond_node = node.child_by_field_name("condition")
        update_node = node.child_by_field_name("increment")
        body_node = node.child_by_field_name("body")

        # Try to detect simple for(let i = 0; i < n; i++) → for i in range(n)
        simple_range = self._try_simple_for_range(init_node, cond_node, update_node)
        if simple_range:
            var_name, start, end, step = simple_range
            if start == "0" and step == "1":
                result = f"{self.indent()}for {var_name} in range({end}):\n"
            elif step == "1":
                result = f"{self.indent()}for {var_name} in range({start}, {end}):\n"
            else:
                result = f"{self.indent()}for {var_name} in range({start}, {end}, {step}):\n"
            if body_node:
                result += self.emit_body(body_node)
            return result

        # Fall back to while loop
        init_expr = ""
        if init_node:
            init_expr = self.emit(init_node)
        cond_expr = self.emit_expr(cond_node) if cond_node else "True"
        update_expr = self.emit_expr(update_node) if update_node else ""

        result = ""
        if init_expr and init_expr.strip():
            result += init_expr
        result += f"{self.indent()}while {cond_expr}:\n"
        if body_node:
            result += self.emit_body(body_node)
        if update_expr:
            self._indent += 1
            result += f"{self.indent()}{update_expr}\n"
            self._indent -= 1
        return result

    def _try_simple_for_range(self, init, cond, update):
        """Try to detect for(let i = start; i < end; i += step)."""
        if not (init and cond and update):
            return None
        try:
            init_text = self.text(init)
            cond_text = self.text(cond)
            update_text = self.text(update)

            # Extract var name and start from init
            m_init = re.match(r"(?:let|const|var)\s+(\w+)\s*=\s*(.+)", init_text)
            if not m_init:
                return None
            var_name = to_snake_case(m_init.group(1))
            start = m_init.group(2).strip().rstrip(";")

            # Extract end from condition
            m_cond = re.match(r"(\w+)\s*<\s*(.+)", cond_text)
            if not m_cond:
                m_cond = re.match(r"(\w+)\s*<=\s*(.+)", cond_text)
                if m_cond:
                    end = f"{self._convert_expr_text(m_cond.group(2).strip())} + 1"
                else:
                    return None
            else:
                end = self._convert_expr_text(m_cond.group(2).strip())

            # Extract step from update
            if re.match(r"\w+\s*\+\+", update_text) or re.match(
                r"\+\+\s*\w+", update_text
            ):
                step = "1"
            elif re.match(r"\w+\s*\+=\s*1\s*$", update_text):
                step = "1"
            else:
                m_step = re.match(r"\w+\s*\+=\s*(.+)", update_text)
                if m_step:
                    step = m_step.group(1).strip()
                else:
                    return None

            return (var_name, self._convert_expr_text(start), end, step)
        except Exception:
            return None

    def _convert_expr_text(self, text: str) -> str:
        """Quick camelCase conversion for simple expressions."""
        return re.sub(r"\b([a-z][a-zA-Z0-9]*)\b", lambda m: to_snake_case(m.group(1)), text)

    def _extract_for_var(self, node) -> str:
        """Extract the variable name from a for-in left side."""
        txt = self.text(node)
        txt = re.sub(r"^(const|let|var)\s+", "", txt)
        # Handle destructuring: { a, b } → (a, b)
        if "{" in txt:
            inner = txt.strip("{}").strip()
            names = [to_snake_case(n.strip().split(":")[0].strip()) for n in inner.split(",") if n.strip()]
            return ", ".join(names)
        return to_snake_case(txt.strip())

    def _emit_while_statement(self, node) -> str:
        cond_node = node.child_by_field_name("condition")
        body_node = node.child_by_field_name("body")
        cond = self.emit_expr(cond_node) if cond_node else "True"
        result = f"{self.indent()}while {cond}:\n"
        if body_node:
            result += self.emit_body(body_node)
        return result

    def _emit_switch_statement(self, node) -> str:
        """switch/case → if/elif chain."""
        disc_node = node.child_by_field_name("value")
        body_node = node.child_by_field_name("body")
        disc = self.emit_expr(disc_node) if disc_node else "None"

        if not body_node:
            return ""

        cases = [c for c in body_node.children if c.type in ("switch_case", "switch_default")]
        result = ""
        first = True
        for case in cases:
            if case.type == "switch_default":
                result += f"{self.indent()}else:\n"
                self._indent += 1
                body = self._emit_case_body(case)
                result += body or (self.indent() + "pass\n")
                self._indent -= 1
            else:
                val_node = case.child_by_field_name("value")
                val = self.emit_expr(val_node) if val_node else "None"
                keyword = "if" if first else "elif"
                result += f"{self.indent()}{keyword} {disc} == {val}:\n"
                self._indent += 1
                body = self._emit_case_body(case)
                result += body or (self.indent() + "pass\n")
                self._indent -= 1
                first = False
        return result

    def _emit_case_body(self, case_node) -> str:
        lines = []
        for child in case_node.children:
            if child.type in ("case", "default", ":", ";"):
                continue
            if self.text(child).strip() == "break":
                continue
            line = self.emit(child)
            if line and line.strip():
                lines.append(line)
        return "\n".join(lines) + "\n" if lines else ""

    def _emit_try_statement(self, node) -> str:
        body_node = node.child_by_field_name("body")
        handler_node = node.child_by_field_name("handler")
        finalizer_node = node.child_by_field_name("finalizer")

        result = f"{self.indent()}try:\n"
        if body_node:
            result += self.emit_body(body_node)

        if handler_node:
            result += f"{self.indent()}except Exception:\n"
            catch_body = handler_node.child_by_field_name("body")
            if catch_body:
                result += self.emit_body(catch_body)
            else:
                self._indent += 1
                result += self.indent() + "pass\n"
                self._indent -= 1
        else:
            result += f"{self.indent()}except Exception:\n"
            self._indent += 1
            result += self.indent() + "pass\n"
            self._indent -= 1

        if finalizer_node:
            result += f"{self.indent()}finally:\n"
            result += self.emit_body(finalizer_node)

        return result

    def _emit_catch_clause(self, node) -> str:
        return self.emit(node.child_by_field_name("body"))

    def _emit_throw_statement(self, node) -> str:
        for child in node.children:
            if child.type in ("throw", ";"):
                continue
            expr = self.emit_expr(child)
            return f"{self.indent()}raise Exception({expr})\n"
        return f"{self.indent()}raise Exception()\n"

    # ------------------------------------------------------------------
    # Variable declarations
    # ------------------------------------------------------------------

    def _emit_lexical_declaration(self, node) -> str:
        """const/let declarations."""
        results = []
        for child in node.children:
            if child.type == "variable_declarator":
                results.append(self._emit_var_declarator(child))
        return "\n".join(results)

    def _emit_variable_declaration(self, node) -> str:
        """var declarations."""
        return self._emit_lexical_declaration(node)

    def _emit_var_declarator(self, node) -> str:
        name_node = node.child_by_field_name("name")
        val_node = node.child_by_field_name("value")

        if name_node and name_node.type == "object_pattern":
            return self._emit_destructuring(name_node, val_node)
        elif name_node and name_node.type == "array_pattern":
            return self._emit_array_destructuring(name_node, val_node)

        name = to_snake_case(self.text(name_node)) if name_node else "_"
        if val_node:
            val = self.emit_expr(val_node)
            return f"{self.indent()}{name} = {val}"
        return f"{self.indent()}{name} = None"

    def _emit_variable_declarator(self, node) -> str:
        return self._emit_var_declarator(node)

    def _emit_destructuring(self, pattern_node, val_node) -> str:
        """const { a, b } = obj → a = obj["a"]; b = obj["b"]"""
        val = self.emit_expr(val_node) if val_node else "None"
        lines = []
        for child in pattern_node.children:
            if child.type == "shorthand_property_identifier_pattern":
                name = self.text(child)
                py_name = to_snake_case(name)
                lines.append(f'{self.indent()}{py_name} = {val}.get("{name}", {val}.get("{py_name}"))')
            elif child.type == "pair_pattern":
                key_node = child.child_by_field_name("key")
                value_node = child.child_by_field_name("value")
                if key_node and value_node:
                    key = self.text(key_node)
                    alias = to_snake_case(self.text(value_node))
                    lines.append(f'{self.indent()}{alias} = {val}["{key}"]')
            elif child.type == "object_assignment_pattern":
                # { a = default } pattern
                left = None
                right = None
                for c in child.children:
                    if c.type == "shorthand_property_identifier_pattern":
                        left = self.text(c)
                    elif c.type == "identifier":
                        left = self.text(c)
                    elif c.type not in ("=",) and right is None and left is not None:
                        right = self.emit_expr(c)
                if left:
                    py_name = to_snake_case(left)
                    default = right or "None"
                    lines.append(
                        f'{self.indent()}{py_name} = {val}.get("{left}", {default})'
                    )
        return "\n".join(lines) if lines else ""

    def _emit_array_destructuring(self, pattern_node, val_node) -> str:
        val = self.emit_expr(val_node) if val_node else "[]"
        names = []
        for child in pattern_node.children:
            if child.type in ("[", "]", ","):
                continue
            names.append(to_snake_case(self.text(child)))
        if names:
            return f"{self.indent()}{', '.join(names)} = {val}"
        return ""

    # ------------------------------------------------------------------
    # Expressions (return strings, no indent prefix)
    # ------------------------------------------------------------------

    def emit_expr(self, node) -> str:
        """Emit an expression node (no indent prefix)."""
        if node is None:
            return ""
        ntype = node.type.replace("-", "_")
        handler = getattr(self, f"_expr_{ntype}", None)
        if handler:
            return handler(node)
        # Try statement handler
        handler2 = getattr(self, f"_emit_{ntype}", None)
        if handler2:
            return handler2(node).strip()
        return self._expr_default(node)

    def _expr_default(self, node) -> str:
        if node.child_count == 0:
            txt = self.text(node)
            # Convert basic JS values
            if txt == "null" or txt == "undefined":
                return "None"
            if txt == "true":
                return "True"
            if txt == "false":
                return "False"
            if txt == "this":
                return "self"
            return txt
        parts = []
        for child in node.children:
            if child.type in (";",):
                continue
            parts.append(self.emit_expr(child))
        return " ".join(p for p in parts if p)

    def _expr_identifier(self, node) -> str:
        name = self.text(node)
        if name == "this":
            return "self"
        if name == "null" or name == "undefined":
            return "None"
        if name == "true":
            return "True"
        if name == "false":
            return "False"
        if name in _PRESERVE_CASE:
            return name
        if name == "Number":
            return "float"
        if name == "console":
            return ""
        return to_snake_case(name)

    def _expr_property_identifier(self, node) -> str:
        name = self.text(node)
        if name in _PRESERVE_CASE:
            return name
        return to_snake_case(name)

    def _expr_shorthand_property_identifier(self, node) -> str:
        name = self.text(node)
        return to_snake_case(name)

    def _expr_number(self, node) -> str:
        return self.text(node)

    def _expr_string(self, node) -> str:
        txt = self.text(node)
        # Convert single-quoted to double-quoted for consistency
        return txt

    def _expr_template_string(self, node) -> str:
        """Convert `template ${expr}` → f"template {expr}"."""
        parts = []
        for child in node.children:
            if child.type == "string_fragment" or child.type == "template_chars":
                parts.append(self.text(child))
            elif child.type == "template_substitution":
                for sc in child.children:
                    if sc.type in ("${", "}"):
                        continue
                    parts.append("{" + self.emit_expr(sc) + "}")
            elif child.type in ("`",):
                continue
            else:
                parts.append(self.text(child))
        return 'f"' + "".join(parts) + '"'

    def _expr_this(self, node) -> str:
        return "self"

    def _expr_true(self, node) -> str:
        return "True"

    def _expr_false(self, node) -> str:
        return "False"

    def _expr_null(self, node) -> str:
        return "None"

    def _expr_undefined(self, node) -> str:
        return "None"

    # ------------------------------------------------------------------
    # Operators
    # ------------------------------------------------------------------

    def _expr_binary_expression(self, node) -> str:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op_node = node.child_by_field_name("operator")
        if not op_node:
            for c in node.children:
                if c.type not in ("identifier", "number", "string", "member_expression",
                                  "call_expression", "parenthesized_expression") and c != left and c != right:
                    op_node = c
                    break

        op = self.text(op_node) if op_node else "+"
        # Convert JS operators to Python
        op = op.replace("===", "==").replace("!==", "!=")
        if op == "instanceof":
            return f"isinstance({self.emit_expr(left)}, {self.emit_expr(right)})"
        if op == "&&":
            op = "and"
        elif op == "||":
            op = "or"
        elif op == "??":
            # Nullish coalescing → or (close enough for most cases)
            l = self.emit_expr(left)
            r = self.emit_expr(right)
            return f"({l} if {l} is not None else {r})"

        return f"{self.emit_expr(left)} {op} {self.emit_expr(right)}"

    def _expr_unary_expression(self, node) -> str:
        op = ""
        operand = None
        for child in node.children:
            if child.type in ("!", "-", "+", "~", "typeof", "void", "delete"):
                op = self.text(child)
            else:
                operand = child
        expr = self.emit_expr(operand) if operand else ""
        if op == "!":
            return f"not {expr}"
        if op == "typeof":
            return f"type({expr}).__name__"
        if op == "void":
            return "None"
        return f"{op}{expr}"

    def _expr_update_expression(self, node) -> str:
        """i++ → i += 1, --i → i -= 1."""
        txt = self.text(node)
        if "++" in txt:
            var = txt.replace("++", "").strip()
            return f"{to_snake_case(var)} += 1"
        elif "--" in txt:
            var = txt.replace("--", "").strip()
            return f"{to_snake_case(var)} -= 1"
        return self._expr_default(node)

    def _expr_ternary_expression(self, node) -> str:
        cond = node.child_by_field_name("condition")
        cons = node.child_by_field_name("consequence")
        alt = node.child_by_field_name("alternative")
        return f"({self.emit_expr(cons)} if {self.emit_expr(cond)} else {self.emit_expr(alt)})"

    def _expr_assignment_expression(self, node) -> str:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        l = self.emit_expr(left) if left else ""
        r = self.emit_expr(right) if right else ""
        # Find operator
        for child in node.children:
            if child.type in ("=", "+=", "-=", "*=", "/=", "&&=", "||=", "??="):
                op = self.text(child)
                if op in ("&&=", "||=", "??="):
                    op = "="
                return f"{l} {op} {r}"
        return f"{l} = {r}"

    def _expr_augmented_assignment_expression(self, node) -> str:
        return self._expr_assignment_expression(node)

    def _expr_parenthesized_expression(self, node) -> str:
        for child in node.children:
            if child.type in ("(", ")"):
                continue
            return f"({self.emit_expr(child)})"
        return "()"

    def _expr_non_null_expression(self, node) -> str:
        """x! → x (TypeScript non-null assertion, just strip)."""
        for child in node.children:
            if child.type == "!":
                continue
            return self.emit_expr(child)
        return ""

    def _expr_type_assertion(self, node) -> str:
        """x as Type → x (strip type assertion)."""
        expr = node.child_by_field_name("expression")
        if expr is None:
            for child in node.children:
                if child.type not in ("as", "type_identifier", "generic_type",
                                       "predefined_type", "object_type"):
                    return self.emit_expr(child)
        return self.emit_expr(expr) if expr else ""

    def _expr_satisfies_expression(self, node) -> str:
        """x satisfies Type → x."""
        for child in node.children:
            if child.type not in ("satisfies",) and not child.type.startswith("type"):
                return self.emit_expr(child)
        return ""

    # ------------------------------------------------------------------
    # Call / member / subscript expressions
    # ------------------------------------------------------------------

    def _expr_call_expression(self, node) -> str:
        func_node = node.child_by_field_name("function")
        args_node = node.child_by_field_name("arguments")

        if func_node and func_node.type == "member_expression":
            return self._emit_method_call(func_node, args_node)

        func = self.emit_expr(func_node) if func_node else ""
        args = self._emit_args(args_node) if args_node else ""

        # Handle known function transformations
        if func == "format":
            # date-fns format(date, pattern) → date if it's just formatting
            arg_list = self._get_arg_list(args_node)
            if len(arg_list) >= 1:
                return f"{self.emit_expr(arg_list[0])}.isoformat()[:10]"

        if func == "parse_date" or func == "parseDate":
            arg_list = self._get_arg_list(args_node)
            if arg_list:
                return f"str({self.emit_expr(arg_list[0])})"

        if func == "is_before" or func == "isBefore":
            arg_list = self._get_arg_list(args_node)
            if len(arg_list) >= 2:
                return f"({self.emit_expr(arg_list[0])} < {self.emit_expr(arg_list[1])})"

        if func == "is_after" or func == "isAfter":
            arg_list = self._get_arg_list(args_node)
            if len(arg_list) >= 2:
                return f"({self.emit_expr(arg_list[0])} > {self.emit_expr(arg_list[1])})"

        if func == "difference_in_days" or func == "differenceInDays":
            arg_list = self._get_arg_list(args_node)
            if len(arg_list) >= 2:
                return f"(({self.emit_expr(arg_list[0])}) - ({self.emit_expr(arg_list[1])})).days if hasattr(({self.emit_expr(arg_list[0])}) - ({self.emit_expr(arg_list[1])}), 'days') else 0"

        if func in ("sort_by", "sortBy"):
            arg_list = self._get_arg_list(args_node)
            if len(arg_list) >= 2:
                return f"sorted({self.emit_expr(arg_list[0])}, key={self.emit_expr(arg_list[1])})"
            elif arg_list:
                return f"sorted({self.emit_expr(arg_list[0])})"

        if func in ("clone_deep", "cloneDeep"):
            arg_list = self._get_arg_list(args_node)
            if arg_list:
                return f"deepcopy({self.emit_expr(arg_list[0])})"

        if func in ("is_number", "isNumber"):
            arg_list = self._get_arg_list(args_node)
            if arg_list:
                return f"isinstance({self.emit_expr(arg_list[0])}, (int, float))"

        if func in ("get_factor", "getFactor"):
            arg_list = self._get_arg_list(args_node)
            if arg_list:
                return f"self._get_factor({self.emit_expr(arg_list[0])})"

        if func in ("get_interval_from_date_range", "getIntervalFromDateRange"):
            arg_list = self._get_arg_list(args_node)
            if arg_list:
                a = ", ".join(self.emit_expr(a) for a in arg_list)
                return f"self._get_interval_from_date_range({a})"

        return f"{func}({args})"

    def _emit_method_call(self, member_node, args_node) -> str:
        """Handle obj.method(args) with Big.js detection."""
        obj_node = member_node.child_by_field_name("object")
        prop_node = member_node.child_by_field_name("property")
        prop_name = self.text(prop_node) if prop_node else ""
        args = self._emit_args(args_node) if args_node else ""
        arg_list = self._get_arg_list(args_node) if args_node else []

        obj = self.emit_expr(obj_node) if obj_node else ""

        # Big.js binary operations: obj.plus(arg) → (obj + arg)
        if prop_name in _BIG_BINARY_OPS and len(arg_list) == 1:
            op = _BIG_BINARY_OPS[prop_name]
            arg = self.emit_expr(arg_list[0])
            return f"({obj} {op} {arg})"

        # Big.js comparison operations
        if prop_name in _BIG_COMPARE_OPS and len(arg_list) == 1:
            op = _BIG_COMPARE_OPS[prop_name]
            arg = self.emit_expr(arg_list[0])
            return f"({obj} {op} {arg})"

        # Big.js unary operations
        if prop_name in _BIG_UNARY and len(arg_list) == 0:
            func = _BIG_UNARY[prop_name]
            if func:
                return f"{func}({obj})"
            return obj

        if prop_name == "toFixed":
            if arg_list:
                return f"round(float({obj}), {self.emit_expr(arg_list[0])})"
            return f"float({obj})"

        # Array methods
        if prop_name == "filter":
            if arg_list:
                fn = self.emit_expr(arg_list[0])
                return f"[x for x in {obj} if ({fn})(x)]"
            return f"{obj}"

        if prop_name == "map":
            if arg_list:
                fn = self.emit_expr(arg_list[0])
                return f"[({fn})(x) for x in {obj}]"
            return f"{obj}"

        if prop_name == "reduce":
            if len(arg_list) >= 2:
                fn = self.emit_expr(arg_list[0])
                init = self.emit_expr(arg_list[1])
                return f"functools.reduce({fn}, {obj}, {init})"
            return f"functools.reduce({self.emit_expr(arg_list[0])}, {obj})"

        if prop_name == "find":
            if arg_list:
                fn = self.emit_expr(arg_list[0])
                return f"next((x for x in {obj} if ({fn})(x)), None)"

        if prop_name == "findIndex":
            if arg_list:
                fn = self.emit_expr(arg_list[0])
                return f"next((i for i, x in enumerate({obj}) if ({fn})(x)), -1)"

        if prop_name == "includes":
            if arg_list:
                return f"({self.emit_expr(arg_list[0])} in {obj})"

        if prop_name == "push":
            if arg_list:
                return f"{obj}.append({self.emit_expr(arg_list[0])})"

        if prop_name == "concat":
            if arg_list:
                return f"{obj} + {self.emit_expr(arg_list[0])}"

        if prop_name == "sort":
            if arg_list:
                return f"{obj}.sort(key=functools.cmp_to_key({self.emit_expr(arg_list[0])}))"
            return f"{obj}.sort()"

        if prop_name == "join":
            if arg_list:
                return f"{self.emit_expr(arg_list[0])}.join({obj})"
            return f"''.join({obj})"

        if prop_name == "at":
            if arg_list:
                return f"{obj}[{self.emit_expr(arg_list[0])}]"

        if prop_name == "substring" or prop_name == "slice":
            if len(arg_list) >= 2:
                return f"{obj}[{self.emit_expr(arg_list[0])}:{self.emit_expr(arg_list[1])}]"
            elif arg_list:
                return f"{obj}[{self.emit_expr(arg_list[0])}:]"

        if prop_name == "localeCompare":
            if arg_list:
                other = self.emit_expr(arg_list[0])
                return f"(({obj} > {other}) - ({obj} < {other}))"

        if prop_name == "getTime":
            return f"{obj}"

        if prop_name == "isoformat":
            return f"{obj}.isoformat()"

        # Object static methods
        if obj == "Object" or obj == "object":
            if prop_name == "keys":
                if arg_list:
                    return f"list({self.emit_expr(arg_list[0])}.keys())"
            elif prop_name == "values":
                if arg_list:
                    return f"list({self.emit_expr(arg_list[0])}.values())"
            elif prop_name == "entries":
                if arg_list:
                    return f"list({self.emit_expr(arg_list[0])}.items())"

        if obj == "Array" or obj == "array":
            if prop_name == "from":
                if arg_list:
                    return f"list({self.emit_expr(arg_list[0])})"

        if obj == "Math" or obj == "math":
            if prop_name == "round":
                if arg_list:
                    return f"round({self.emit_expr(arg_list[0])})"
            elif prop_name == "min":
                return f"min({args})"
            elif prop_name == "max":
                return f"max({args})"
            elif prop_name == "abs":
                if arg_list:
                    return f"abs({self.emit_expr(arg_list[0])})"
            elif prop_name == "floor":
                if arg_list:
                    return f"int({self.emit_expr(arg_list[0])})"

        if obj == "JSON":
            if prop_name == "parse":
                return f"json.loads({args})"
            elif prop_name == "stringify":
                return f"json.dumps({args})"

        # Logger methods → comment or pass
        if obj == "" and prop_name in ("log", "warn", "error", "debug"):
            return "pass"

        py_prop = to_snake_case(prop_name) if prop_name not in _PRESERVE_CASE else prop_name
        return f"{obj}.{py_prop}({args})"

    def _emit_args(self, args_node) -> str:
        """Emit function arguments."""
        if args_node is None:
            return ""
        parts = []
        for child in args_node.children:
            if child.type in ("(", ")", ","):
                continue
            if child.type == "type_annotation":
                continue
            parts.append(self.emit_expr(child))
        return ", ".join(parts)

    def _get_arg_list(self, args_node):
        """Get list of argument nodes."""
        if args_node is None:
            return []
        return [c for c in args_node.children if c.type not in ("(", ")", ",")]

    def _expr_member_expression(self, node) -> str:
        obj_node = node.child_by_field_name("object")
        prop_node = node.child_by_field_name("property")

        obj = self.emit_expr(obj_node) if obj_node else ""
        prop = self.text(prop_node) if prop_node else ""

        # Check for optional chaining (?.)
        is_optional = any(self.text(c) == "?." for c in node.children if c.type == "optional_chain")

        # Special property translations
        if prop == "length":
            return f"len({obj})"

        if prop == "EPSILON":
            return "1e-15"

        py_prop = to_snake_case(prop) if prop not in _PRESERVE_CASE else prop

        if is_optional:
            return f"(getattr({obj}, '{py_prop}', None))"

        # Handle dict-like access for known patterns
        if obj == "self":
            return f"self.{py_prop}"

        return f"{obj}.{py_prop}"

    def _expr_subscript_expression(self, node) -> str:
        """obj[key] → obj[key]."""
        obj_node = node.child_by_field_name("object")
        index_node = node.child_by_field_name("index")
        obj = self.emit_expr(obj_node) if obj_node else ""
        index = self.emit_expr(index_node) if index_node else ""
        # Check for optional chaining
        is_optional = "?." in self.text(node)
        if is_optional:
            return f"({obj}.get({index}) if {obj} is not None else None)"
        return f"{obj}[{index}]"

    def _expr_new_expression(self, node) -> str:
        """new X(args) → X(args), with Big → Decimal."""
        constructor_node = node.child_by_field_name("constructor")
        args_node = node.child_by_field_name("arguments")

        constructor = self.text(constructor_node) if constructor_node else ""
        args = self._emit_args(args_node) if args_node else ""

        if constructor == "Big":
            if args and args != "0":
                return f"Decimal(str({args}))"
            return f"Decimal({args})"
        if constructor == "Date":
            if not args:
                return "date.today()"
            return f"str({args})"
        if constructor == "Set":
            return f"set({args})" if args else "set()"
        if constructor == "Map":
            return f"dict({args})" if args else "{}"

        return f"{constructor}({args})"

    def _expr_object(self, node) -> str:
        """Object literal → dict literal."""
        pairs = []
        for child in node.children:
            if child.type == "pair":
                key_node = child.child_by_field_name("key")
                val_node = child.child_by_field_name("value")
                key = self.text(key_node) if key_node else ""
                val = self.emit_expr(val_node) if val_node else "None"
                # Quote string keys
                if key_node and key_node.type in ("property_identifier", "identifier"):
                    pairs.append(f'"{key}": {val}')
                else:
                    pairs.append(f"{self.emit_expr(key_node)}: {val}")
            elif child.type == "shorthand_property_identifier":
                name = self.text(child)
                py_name = to_snake_case(name)
                pairs.append(f'"{name}": {py_name}')
            elif child.type == "spread_element":
                for sc in child.children:
                    if sc.type == "...":
                        continue
                    pairs.append(f"**{self.emit_expr(sc)}")
            elif child.type == "method_definition":
                # Skip inline method definitions in object literals
                continue
        return "{" + ", ".join(pairs) + "}"

    def _expr_array(self, node) -> str:
        """Array literal → list literal."""
        items = []
        for child in node.children:
            if child.type in ("[", "]", ","):
                continue
            if child.type == "spread_element":
                for sc in child.children:
                    if sc.type == "...":
                        continue
                    items.append(f"*{self.emit_expr(sc)}")
            else:
                items.append(self.emit_expr(child))
        return "[" + ", ".join(items) + "]"

    def _expr_arrow_function(self, node) -> str:
        return self._emit_arrow_function(node)

    def _expr_spread_element(self, node) -> str:
        for child in node.children:
            if child.type == "...":
                continue
            return f"*{self.emit_expr(child)}"
        return ""

    def _expr_await_expression(self, node) -> str:
        """Strip await — our Python code is synchronous."""
        for child in node.children:
            if child.type == "await":
                continue
            return self.emit_expr(child)
        return ""

    def _expr_as_expression(self, node) -> str:
        """x as Type → x."""
        return self.emit_expr(node.children[0]) if node.children else ""

    # ------------------------------------------------------------------
    # Type annotations (strip)
    # ------------------------------------------------------------------

    def _emit_type_annotation(self, node) -> str:
        return ""

    def _emit_type_alias_declaration(self, node) -> str:
        return ""

    def _emit_interface_declaration(self, node) -> str:
        return ""

    def _emit_enum_declaration(self, node) -> str:
        return ""

    def _expr_type_annotation(self, node) -> str:
        return ""

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def _emit_comment(self, node) -> str:
        txt = self.text(node)
        if txt.startswith("//"):
            return f"{self.indent()}# {txt[2:].strip()}\n"
        if txt.startswith("/*"):
            inner = txt[2:-2].strip()
            lines = inner.split("\n")
            result = ""
            for line in lines:
                cleaned = line.strip().lstrip("* ")
                if cleaned:
                    result += f"{self.indent()}# {cleaned}\n"
            return result
        return ""

    def _emit_empty_statement(self, node) -> str:
        return ""

    def _emit_break_statement(self, node) -> str:
        return f"{self.indent()}break\n"

    def _emit_continue_statement(self, node) -> str:
        return f"{self.indent()}continue\n"

    def _emit_labeled_statement(self, node) -> str:
        """Skip labels, emit the body."""
        body = node.child_by_field_name("body")
        return self.emit(body) if body else ""

    def _emit_decorator(self, node) -> str:
        return ""

    def _expr_regex(self, node) -> str:
        txt = self.text(node)
        # /pattern/flags → re.compile("pattern")
        m = re.match(r"/(.+)/(\w*)", txt)
        if m:
            pattern = m.group(1)
            return f're.compile(r"{pattern}")'
        return f're.compile(r"{txt}")'
