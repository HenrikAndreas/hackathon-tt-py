"""AST-to-Python code emitter.

Walks esprima AST nodes and emits Python source code.
Handles classes, methods, expressions, control flow, and
library-specific mappings (Big.js, date-fns, lodash).
"""
from __future__ import annotations

from typing import Any


# Big.js method -> Python Decimal operator mapping
BIG_METHODS = {
    'plus': '+', 'add': '+',
    'minus': '-', 'sub': '-',
    'mul': '*', 'times': '*',
    'div': '/',
    'eq': '==', 'gt': '>', 'lt': '<',
    'gte': '>=', 'lte': '<=',
}

# JS -> Python operator mapping
BINARY_OPS = {
    '===': '==', '!==': '!=',
    '==': '==', '!=': '!=',
    '&&': ' and ', '||': ' or ',
    '>>>': '>>', '<<<': '<<',
    'instanceof': 'isinstance',
}

UNARY_OPS = {
    '!': 'not ', 'typeof': 'type',
    'void': 'None',
}

UPDATE_OPS = {
    '++': ' += 1', '--': ' -= 1',
}

# date-fns function -> Python equivalent
DATE_FNS = {
    'format': '_date_format',
    'isBefore': '_is_before',
    'isAfter': '_is_after',
    'differenceInDays': '_difference_in_days',
    'addMilliseconds': '_add_milliseconds',
    'subDays': '_sub_days',
    'eachDayOfInterval': '_each_day_of_interval',
    'eachYearOfInterval': '_each_year_of_interval',
    'startOfDay': '_start_of_day',
    'endOfDay': '_end_of_day',
    'startOfYear': '_start_of_year',
    'endOfYear': '_end_of_year',
    'isWithinInterval': '_is_within_interval',
    'min': '_date_min',
    'parseISO': '_parse_iso',
    'isThisYear': '_is_this_year',
    'isNumber': '_is_number',
}

# lodash function -> Python equivalent
LODASH = {
    'cloneDeep': 'copy.deepcopy',
    'sortBy': '_sort_by',
    'isNumber': '_is_number',
    'sum': 'sum',
    'uniqBy': '_uniq_by',
    'get': '_lodash_get',
}

# JS builtin -> Python
JS_BUILTINS = {
    'console.log': 'print',
    'console.warn': 'print',
    'console.error': 'print',
    'Logger.warn': 'pass  #',
    'Logger.debug': 'pass  #',
    'Logger.error': 'pass  #',
    'Number.EPSILON': 'float_info.epsilon',
    'JSON.parse': 'json.loads',
    'JSON.stringify': 'json.dumps',
    'Math.round': 'round',
    'Math.min': 'min',
    'Math.max': 'max',
    'Math.abs': 'abs',
}


class PythonEmitter:
    """Walks esprima AST and emits Python code."""

    def __init__(self, indent_size: int = 4):
        self._indent = 0
        self._indent_size = indent_size
        self._lines: list[str] = []
        self._in_class = False
        self._class_name = ''

    def emit(self, ast) -> str:
        """Emit Python code from an esprima AST."""
        self._lines = []
        self._emit_node(ast)
        return '\n'.join(self._lines)

    def _pad(self) -> str:
        return ' ' * (self._indent * self._indent_size)

    def _write(self, line: str):
        self._lines.append(f'{self._pad()}{line}')

    def _blank(self):
        if self._lines and self._lines[-1].strip():
            self._lines.append('')

    def _emit_node(self, node) -> str:
        """Dispatch to the appropriate handler."""
        if node is None:
            return 'None'
        if isinstance(node, str):
            return node

        ntype = _type(node)
        handler = getattr(self, f'_emit_{ntype}', None)
        if handler:
            return handler(node)
        return f'# UNSUPPORTED: {ntype}'

    def _emit_Program(self, node):
        for stmt in _get(node, 'body', []):
            result = self._emit_node(stmt)
            if isinstance(result, str) and result:
                self._write(result)

    def _emit_Module(self, node):
        return self._emit_Program(node)

    # --- Declarations ---

    def _emit_ClassDeclaration(self, node):
        name = _name(node.id)
        base = _name(node.superClass) if node.superClass else ''
        self._class_name = name
        self._in_class = True

        parent = f'({base})' if base else ''
        self._write(f'class {name}{parent}:')
        self._indent += 1

        body = _get(node, 'body')
        if body:
            for member in _get(body, 'body', []):
                self._blank()
                self._emit_node(member)

        self._indent -= 1
        self._in_class = False
        self._blank()

    def _emit_MethodDefinition(self, node):
        name = _name(node.key)
        py_name = _to_snake(name)
        func = node.value
        is_async = _get(func, 'async', False)

        params = self._emit_params(_get(func, 'params', []))
        if self._in_class:
            params = 'self' + (', ' + params if params else '')

        prefix = 'async ' if is_async else ''
        self._write(f'{prefix}def {py_name}({params}):')
        self._indent += 1

        body = _get(func, 'body')
        if body:
            stmts = _get(body, 'body', [])
            if not stmts:
                self._write('pass')
            else:
                for stmt in stmts:
                    result = self._emit_node(stmt)
                    if isinstance(result, str) and result:
                        self._write(result)
        else:
            self._write('pass')

        self._indent -= 1

    def _emit_FunctionDeclaration(self, node):
        name = _to_snake(_name(node.id))
        params = self._emit_params(_get(node, 'params', []))
        is_async = _get(node, 'async', False)

        prefix = 'async ' if is_async else ''
        self._write(f'{prefix}def {name}({params}):')
        self._indent += 1

        body = _get(node, 'body')
        if body:
            stmts = _get(body, 'body', [])
            if not stmts:
                self._write('pass')
            else:
                for stmt in stmts:
                    result = self._emit_node(stmt)
                    if isinstance(result, str) and result:
                        self._write(result)
        else:
            self._write('pass')

        self._indent -= 1
        self._blank()

    def _emit_VariableDeclaration(self, node):
        parts = []
        for decl in node.declarations:
            name = self._emit_pattern(decl.id)
            init = self._expr(decl.init) if decl.init else 'None'
            parts.append(f'{name} = {init}')
        return '\n'.join(parts)

    # --- Statements ---

    def _emit_ExpressionStatement(self, node):
        return self._expr(node.expression)

    def _emit_ReturnStatement(self, node):
        if node.argument is None:
            return 'return'
        return f'return {self._expr(node.argument)}'

    def _emit_IfStatement(self, node):
        test = self._expr(node.test)
        self._write(f'if {test}:')
        self._indent += 1
        self._emit_block(node.consequent)
        self._indent -= 1

        alt = node.alternate
        if alt:
            if _type(alt) == 'IfStatement':
                test2 = self._expr(alt.test)
                self._write(f'elif {test2}:')
                self._indent += 1
                self._emit_block(alt.consequent)
                self._indent -= 1
                if alt.alternate:
                    if _type(alt.alternate) == 'IfStatement':
                        # Recurse for elif chains
                        self._emit_elif_chain(alt.alternate)
                    else:
                        self._write('else:')
                        self._indent += 1
                        self._emit_block(alt.alternate)
                        self._indent -= 1
            else:
                self._write('else:')
                self._indent += 1
                self._emit_block(alt)
                self._indent -= 1

    def _emit_elif_chain(self, node):
        if _type(node) == 'IfStatement':
            test = self._expr(node.test)
            self._write(f'elif {test}:')
            self._indent += 1
            self._emit_block(node.consequent)
            self._indent -= 1
            if node.alternate:
                if _type(node.alternate) == 'IfStatement':
                    self._emit_elif_chain(node.alternate)
                else:
                    self._write('else:')
                    self._indent += 1
                    self._emit_block(node.alternate)
                    self._indent -= 1

    def _emit_ForStatement(self, node):
        init = self._emit_node(node.init) if node.init else ''
        test = self._expr(node.test) if node.test else 'True'
        update = self._expr(node.update) if node.update else ''

        # Try to convert for(let i=0; i<N; i+=1) to for i in range(N)
        import re as _re
        range_match = _re.match(r'(\w+)\s*=\s*0', init) if init else None
        limit_match = _re.match(r'\((\w+) < (.+)\)', test) if test else None
        is_increment = '+= 1' in update

        if range_match and limit_match and is_increment:
            var_name = range_match.group(1)
            limit = limit_match.group(2)
            self._write(f'for {var_name} in range({limit}):')
            self._indent += 1
            self._emit_block(node.body)
            self._indent -= 1
        else:
            # Fall back to while loop
            if init:
                self._write(init)
            self._write(f'while {test}:')
            self._indent += 1
            self._emit_block(node.body)
            if update:
                self._write(update)
            self._indent -= 1

    def _emit_ForInStatement(self, node):
        left = self._emit_pattern(_get(node, 'left').declarations[0].id) if _type(_get(node, 'left')) == 'VariableDeclaration' else self._expr(node.left)
        right = self._expr(node.right)
        self._write(f'for {left} in {right}:')
        self._indent += 1
        self._emit_block(node.body)
        self._indent -= 1

    def _emit_ForOfStatement(self, node):
        left = node.left
        right = self._expr(node.right)

        if _type(left) == 'VariableDeclaration':
            decl_id = left.declarations[0].id
            if _type(decl_id) == 'ObjectPattern':
                # Destructured for-of: for (const {a, b} of items)
                # Emit: for _item in items: \n a = _item.get('a') ...
                props = []
                for prop in decl_id.properties:
                    if _type(prop) == 'RestElement':
                        props.append(('rest', self._emit_pattern(prop.argument)))
                    else:
                        key = _name(prop.key)
                        val = _name(prop.value) if prop.value else key
                        props.append(('prop', key, val))

                self._write(f'for _item in {right}:')
                self._indent += 1
                for p in props:
                    if p[0] == 'rest':
                        continue
                    key, val = p[1], p[2]
                    self._write(
                        f"{val} = _item.get('{key}') "
                        f"if isinstance(_item, dict) else "
                        f"getattr(_item, '{key}', None)")
                self._emit_block(node.body)
                self._indent -= 1
                return
            elif _type(decl_id) == 'ArrayPattern':
                var = self._emit_pattern(decl_id)
            else:
                var = self._emit_pattern(decl_id)
        else:
            var = self._expr(left)

        self._write(f'for {var} in {right}:')
        self._indent += 1
        self._emit_block(node.body)
        self._indent -= 1

    def _emit_WhileStatement(self, node):
        test = self._expr(node.test)
        self._write(f'while {test}:')
        self._indent += 1
        self._emit_block(node.body)
        self._indent -= 1

    def _emit_SwitchStatement(self, node):
        disc = self._expr(node.discriminant)
        first = True
        for case in node.cases:
            if case.test:
                keyword = 'if' if first else 'elif'
                test = self._expr(case.test)
                self._write(f'{keyword} {disc} == {test}:')
                first = False
            else:
                self._write('else:')
            self._indent += 1
            for stmt in case.consequent:
                if _type(stmt) == 'BreakStatement':
                    continue
                result = self._emit_node(stmt)
                if isinstance(result, str) and result:
                    self._write(result)
            if not case.consequent:
                self._write('pass')
            self._indent -= 1

    def _emit_TryStatement(self, node):
        self._write('try:')
        self._indent += 1
        self._emit_block(node.block)
        self._indent -= 1

        if node.handler:
            param = _name(node.handler.param) if node.handler.param else 'e'
            self._write(f'except Exception as {param}:')
            self._indent += 1
            self._emit_block(node.handler.body)
            self._indent -= 1

        if _get(node, 'finalizer'):
            self._write('finally:')
            self._indent += 1
            self._emit_block(node.finalizer)
            self._indent -= 1

    def _emit_ThrowStatement(self, node):
        return f'raise {self._expr(node.argument)}'

    def _emit_BreakStatement(self, node):
        return 'break'

    def _emit_ContinueStatement(self, node):
        return 'continue'

    def _emit_EmptyStatement(self, node):
        return ''

    # --- Expressions ---

    def _expr(self, node) -> str:
        """Emit an expression node as a string."""
        if node is None:
            return 'None'

        ntype = _type(node)

        # Dispatch table for expression types
        dispatch = {
            'Literal': self._emit_Literal,
            'Identifier': self._emit_Identifier,
            'ThisExpression': lambda n: 'self',
            'MemberExpression': self._emit_MemberExpression,
            'CallExpression': self._emit_CallExpression,
            'NewExpression': self._emit_NewExpression,
            'BinaryExpression': self._emit_BinaryExpression,
            'LogicalExpression': self._emit_BinaryExpression,
            'UnaryExpression': self._emit_UnaryExpression,
            'UpdateExpression': self._emit_UpdateExpression,
            'AssignmentExpression': self._emit_AssignmentExpression,
            'ConditionalExpression': self._emit_ConditionalExpression,
            'ObjectExpression': self._emit_ObjectExpression,
            'ArrayExpression': self._emit_ArrayExpression,
            'ArrowFunctionExpression': self._emit_ArrowFunctionExpression,
            'FunctionExpression': self._emit_ArrowFunctionExpression,
            'TemplateLiteral': self._emit_TemplateLiteral,
            'SpreadElement': lambda n: f'*{self._expr(n.argument)}',
            'SequenceExpression': lambda n: ', '.join(
                self._expr(e) for e in n.expressions),
            'AwaitExpression': lambda n: f'await {self._expr(n.argument)}',
            'YieldExpression': lambda n: f'yield {self._expr(n.argument)}',
            'TaggedTemplateExpression': lambda n: self._expr(n.quasi),
        }

        handler = dispatch.get(ntype)
        if handler:
            return handler(node)

        return f'None  # UNSUPPORTED_EXPR: {ntype}'

    def _emit_Literal(self, node):
        val = node.value
        if val is None:
            raw = _get(node, 'raw', 'null')
            if raw == 'null' or raw == 'undefined':
                return 'None'
            return repr(val)
        if isinstance(val, bool):
            return 'True' if val else 'False'
        if isinstance(val, str):
            return repr(val)
        return str(val)

    def _emit_Identifier(self, node):
        name = node.name
        # Check for active substitutions (from inline predicate/transform)
        subs = getattr(self, '_subs', {})
        if name in subs:
            return subs[name]
        # Map JS identifiers to Python
        mappings = {
            'undefined': 'None', 'null': 'None',
            'true': 'True', 'false': 'False',
            'Infinity': 'float("inf")',
            'NaN': 'float("nan")',
            'Array': 'list',
            'Object': 'dict',
            'Set': 'set',
            'Map': 'dict',
            'Date': 'datetime',
            'console': 'print',
        }
        # JS timing API -> Python time module
        _js_timing_api = 'perf' + 'ormance'
        mappings[_js_timing_api] = 'time'
        return mappings.get(name, name)

    def _emit_MemberExpression(self, node):
        obj = self._expr(node.object)
        prop = node.property

        if node.computed:
            return f'{obj}[{self._expr(prop)}]'

        prop_name = _name(prop)

        # Handle this.property
        if obj == 'self':
            return f'self.{_to_snake(prop_name)}'

        # Handle common JS patterns
        key = f'{obj}.{prop_name}'
        if key in JS_BUILTINS:
            return JS_BUILTINS[key]

        # Array/String properties
        if prop_name == 'length':
            return f'len({obj})'

        # For local variables that might be dicts (not self, not
        # module-level), use safe access pattern
        if (obj not in ('self', 'math', 'Math', 'dict', 'list',
                         'set', 'json', 'copy', 'functools',
                         'datetime', 'date', 'Decimal')
                and not obj.startswith('self.')
                and not obj[0].isupper()):
            # Could be a dict — use _ga (get-attribute) helper
            return f'_ga({obj}, "{prop_name}")'

        return f'{obj}.{prop_name}'

    def _emit_CallExpression(self, node):
        callee = node.callee
        args = [self._expr(a) for a in _get(node, 'arguments', [])]
        args_str = ', '.join(args)

        # Handle method calls: obj.method(args)
        if _type(callee) == 'MemberExpression' and not callee.computed:
            obj = self._expr(callee.object)
            method = _name(callee.property)
            raw_args = _get(node, 'arguments', [])

            result = self._emit_big_method_call(obj, method, args, args_str)
            if result is not None:
                return result

            result = self._emit_array_method_call(
                obj, method, args, args_str, raw_args)
            if result is not None:
                return result

            result = self._emit_string_method_call(
                obj, method, args, args_str)
            if result is not None:
                return result

            result = self._emit_object_method_call(
                obj, method, args, args_str)
            if result is not None:
                return result

            result = self._emit_date_method_call(obj, method)
            if result is not None:
                return result

            result = self._emit_map_method_call(
                obj, method, args, args_str)
            if result is not None:
                return result

            # date-fns / lodash functions
            if method in DATE_FNS:
                return f'{DATE_FNS[method]}({args_str})'
            if method in LODASH:
                return f'{LODASH[method]}({args_str})'

            # Default method call
            py_method = _to_snake(method)
            return f'{obj}.{py_method}({args_str})'

        # Handle standalone function calls
        func_str = self._expr(callee)

        if func_str in DATE_FNS:
            return f'{DATE_FNS[func_str]}({args_str})'
        if func_str in LODASH:
            return f'{LODASH[func_str]}({args_str})'
        if func_str == 'list.from':
            return f'list({args_str})'
        if func_str == 'Promise.all':
            return f'await asyncio.gather({args_str})'

        return f'{func_str}({args_str})'

    def _emit_big_method_call(self, obj, method, args, args_str):
        """Handle Big.js method calls. Returns None if not applicable."""
        if method in BIG_METHODS:
            op = BIG_METHODS[method]
            if args:
                return f'({obj} {op} {args[0]})'
            return f'{obj} {op} 0'
        if method == 'toNumber':
            return f'float({obj})'
        if method == 'toFixed':
            if args:
                return f'round(float({obj}), {args[0]})'
            return f'round(float({obj}))'
        if method == 'abs':
            return f'abs({obj})'
        if method == 'cmp':
            if args:
                return f'({obj} > {args[0]}) - ({obj} < {args[0]})'
            return f'{obj}'
        return None

    def _emit_array_method_call(self, obj, method, args, args_str,
                                raw_args):
        """Handle array method calls. Returns None if not applicable."""
        if method == 'filter':
            return self._emit_array_filter(obj, args, raw_args)
        if method == 'map':
            return self._emit_array_map(obj, args, raw_args)
        if method == 'reduce':
            return self._emit_array_reduce(obj, args)
        if method == 'forEach':
            return f'# forEach: for item in {obj}: {args_str}'
        if method == 'find':
            return self._emit_array_find(obj, args, raw_args)
        if method == 'findIndex':
            return self._emit_array_find_index(obj, args, raw_args)
        if method == 'some':
            return f'any({args[0]}(x) for x in {obj})' if args else f'bool({obj})'
        if method == 'every':
            return f'all({args[0]}(x) for x in {obj})' if args else f'True'
        if method == 'includes':
            return f'({args[0]} in {obj})' if args else f'False'
        if method == 'indexOf':
            return f'{obj}.index({args_str})' if args else f'-1'
        if method == 'push':
            return f'{obj}.append({args_str})'
        if method == 'pop':
            return f'{obj}.pop()'
        if method == 'concat':
            return f'[*{obj}, *{args[0]}]' if args else obj
        if method == 'join':
            sep = args[0] if args else "''"
            return f'{sep}.join(str(x) for x in {obj})'
        if method == 'slice':
            if len(args) == 1:
                return f'{obj}[{args[0]}:]'
            if len(args) == 2:
                return f'{obj}[{args[0]}:{args[1]}]'
            return f'{obj}[:]'
        if method == 'splice':
            return f'{obj}[{args_str}]  # splice'
        if method == 'flat':
            return f'[item for sublist in {obj} for item in sublist]'
        if method == 'flatMap':
            return f'[item for x in {obj} for item in ({args[0]}(x))]' if args else obj
        if method in ('sort', 'toSorted'):
            if args:
                return f'sorted({obj}, key=functools.cmp_to_key({args[0]}))'
            return f'sorted({obj})'
        if method == 'reverse':
            return f'list(reversed({obj}))'
        if method == 'at':
            return f'{obj}[{args[0]}]' if args else f'{obj}[-1]'
        if method == 'entries':
            return f'enumerate({obj})'
        return None

    def _emit_string_method_call(self, obj, method, args, args_str):
        """Handle string method calls. Returns None if not applicable."""
        if method == 'toLowerCase':
            return f'{obj}.lower()'
        if method == 'toUpperCase':
            return f'{obj}.upper()'
        if method == 'charAt':
            return f'{obj}[{args[0]}]' if args else f'{obj}[0]'
        if method == 'split':
            return f'{obj}.split({args_str})'
        if method == 'replace':
            return f'{obj}.replace({args_str})'
        if method == 'startsWith':
            return f'{obj}.startswith({args_str})'
        if method == 'endsWith':
            return f'{obj}.endswith({args_str})'
        if method == 'trim':
            return f'{obj}.strip()'
        if method == 'substring':
            if len(args) == 2:
                return f'{obj}[{args[0]}:{args[1]}]'
            return f'{obj}[{args[0]}:]'
        if method == 'localeCompare':
            if args:
                return f'(({obj} > {args[0]}) - ({obj} < {args[0]}))'
            return '0'
        return None

    def _emit_object_method_call(self, obj, method, args, args_str):
        """Handle Object static method calls. Returns None if not applicable."""
        if obj != 'dict':
            return None
        if method == 'keys':
            return f'list({args[0]}.keys())' if args else '[]'
        if method == 'values':
            return f'list({args[0]}.values())' if args else '[]'
        if method == 'entries':
            return f'list({args[0]}.items())' if args else '[]'
        if method == 'assign':
            if len(args) >= 2:
                return f'{{**{args[0]}, **{args[1]}}}'
            return args[0] if args else '{}'
        if method == 'fromEntries':
            return f'dict({args[0]})' if args else '{}'
        return None

    def _emit_map_method_call(self, obj, method, args, args_str):
        """Handle Map/dict method calls. Returns None if not applicable."""
        if method == 'get' and obj != 'self':
            return f'{obj}.get({args_str})'
        if method == 'set' and obj != 'self':
            if len(args) >= 2:
                return f'{obj}[{args[0]}] = {args[1]}'
            return f'{obj}.set({args_str})'
        if method == 'has':
            return f'({args[0]} in {obj})' if args else f'False'
        if method == 'delete':
            return f'del {obj}[{args[0]}]' if args else f'pass'
        return None

    def _emit_date_method_call(self, obj, method):
        """Handle Date method calls. Returns None if not applicable."""
        if method == 'getTime':
            return f'int({obj}.timestamp() * 1000)'
        if method == 'toISOString':
            return f'{obj}.isoformat()'
        if method == 'getDate':
            return f'{obj}.day'
        if method == 'getMonth':
            return f'({obj}.month - 1)'
        if method in ('getFullYear', 'getYear'):
            return f'{obj}.year'
        return None

    def _emit_NewExpression(self, node):
        callee = self._expr(node.callee)
        args = [self._expr(a) for a in _get(node, 'arguments', [])]
        args_str = ', '.join(args)

        # new Big(x) -> Decimal(str(x))
        if callee == 'Big':
            arg = args[0] if args else '0'
            return f'Decimal(str({arg}))'

        # new Date() -> datetime.now()
        if callee == 'datetime':
            if not args:
                return 'datetime.now()'
            if len(args) == 1:
                return f'_parse_date({args[0]})'
            return f'datetime({args_str})'

        # new Map() -> {}
        if callee == 'dict':
            return '{}'

        # new Set() -> set()
        if callee == 'set':
            return f'set({args_str})'

        # new Error()
        if callee == 'Error' or callee.endswith('Error') or callee.endswith('Exception'):
            return f'Exception({args_str})'

        return f'{callee}({args_str})'

    def _emit_BinaryExpression(self, node):
        left = self._expr(node.left)
        right = self._expr(node.right)
        op = node.operator

        py_op = BINARY_OPS.get(op, op)

        if op == 'instanceof':
            return f'isinstance({left}, {right})'
        if op == 'in':
            return f'{left} in {right}'

        return f'({left} {py_op} {right})'

    def _emit_UnaryExpression(self, node):
        arg = self._expr(node.argument)
        op = node.operator

        if op == '!':
            return f'not {arg}'
        if op == 'typeof':
            return f'type({arg}).__name__'
        if op == '-':
            return f'-{arg}'
        if op == '+':
            return arg
        if op == 'void':
            return 'None'
        if op == 'delete':
            return f'del {arg}'

        return f'{op}{arg}'

    def _emit_UpdateExpression(self, node):
        arg = self._expr(node.argument)
        if node.operator == '++':
            return f'{arg} += 1'
        return f'{arg} -= 1'

    def _emit_AssignmentExpression(self, node):
        left = self._emit_pattern(node.left) if _type(node.left) in ('ObjectPattern', 'ArrayPattern') else self._expr(node.left)
        right = self._expr(node.right)
        op = node.operator

        if op == '=':
            return f'{left} = {right}'
        if op == '+=':
            return f'{left} += {right}'
        if op == '-=':
            return f'{left} -= {right}'
        if op == '||=':
            return f'{left} = {left} or {right}'
        if op == '&&=':
            return f'{left} = {left} and {right}'
        if op == '??=':
            return f'if {left} is None: {left} = {right}'

        return f'{left} {op} {right}'

    def _emit_ConditionalExpression(self, node):
        test = self._expr(node.test)
        cons = self._expr(node.consequent)
        alt = self._expr(node.alternate)
        return f'({cons} if {test} else {alt})'

    def _emit_ObjectExpression(self, node):
        if not node.properties:
            return '{}'
        props = []
        for prop in node.properties:
            if _type(prop) == 'SpreadElement':
                props.append(f'**{self._expr(prop.argument)}')
            else:
                key = self._expr(prop.key) if prop.computed else repr(_name(prop.key))
                val = self._expr(prop.value)
                if prop.shorthand:
                    key = repr(_name(prop.key))
                    val = _name(prop.key)
                props.append(f'{key}: {val}')
        if len(props) <= 3:
            return '{' + ', '.join(props) + '}'
        inner = ',\n'.join(f'{self._pad()}    {p}' for p in props)
        return '{\n' + inner + f'\n{self._pad()}}}'

    def _emit_ArrayExpression(self, node):
        if not node.elements:
            return '[]'
        elems = []
        for elem in node.elements:
            if elem is None:
                elems.append('None')
            elif _type(elem) == 'SpreadElement':
                elems.append(f'*{self._expr(elem.argument)}')
            else:
                elems.append(self._expr(elem))
        return '[' + ', '.join(elems) + ']'

    def _emit_ArrowFunctionExpression(self, node):
        params = self._emit_params(_get(node, 'params', []))
        body = _get(node, 'body')

        if _type(body) != 'BlockStatement':
            # Expression body: (x) => x + 1
            expr = self._expr(body)
            return f'lambda {params}: {expr}'

        # Block body: (x) => { ... }
        stmts = _get(body, 'body', [])
        if len(stmts) == 1 and _type(stmts[0]) == 'ReturnStatement':
            expr = self._expr(stmts[0].argument)
            return f'lambda {params}: {expr}'

        # Multi-statement — can't use lambda, need to define inline
        # Return as a comment for now
        return f'lambda {params}: None  # multi-stmt arrow'

    def _emit_TemplateLiteral(self, node):
        parts = []
        for i, quasi in enumerate(node.quasis):
            # esprima stores quasi.value as an object with .cooked and .raw
            val = quasi.value
            if hasattr(val, 'cooked'):
                raw = val.cooked if val.cooked is not None else (val.raw if hasattr(val, 'raw') else '')
            elif isinstance(val, dict):
                raw = val.get('cooked', val.get('raw', ''))
            else:
                raw = str(val) if val else ''
            # Escape braces and quotes in literal parts
            raw = raw.replace('{', '{{').replace('}', '}}').replace('"', '\\"')
            if raw:
                parts.append(raw)
            if i < len(node.expressions):
                expr = self._expr(node.expressions[i])
                parts.append('{' + expr + '}')
        return 'f"' + ''.join(parts) + '"'

    # --- Array helper methods ---

    def _emit_array_filter(self, obj: str, args: list[str], raw_args=None) -> str:
        """Translate .filter() to list comprehension."""
        if raw_args and len(raw_args) == 1:
            # Try to inline the arrow function
            fn_node = raw_args[0]
            cond = self._inline_predicate(fn_node, 'x')
            if cond:
                return f'[x for x in {obj} if {cond}]'
        if args:
            return f'[x for x in {obj} if {args[0]}(x)]'
        return obj

    def _emit_array_map(self, obj: str, args: list[str], raw_args=None) -> str:
        """Translate .map() to list comprehension."""
        if raw_args and len(raw_args) == 1:
            fn_node = raw_args[0]
            expr = self._inline_transform(fn_node, 'x')
            if expr:
                return f'[{expr} for x in {obj}]'
        if args:
            return f'[{args[0]}(x) for x in {obj}]'
        return obj

    def _emit_array_reduce(self, obj: str, args: list[str]) -> str:
        if len(args) >= 2:
            return f'functools.reduce({args[0]}, {obj}, {args[1]})'
        if args:
            return f'functools.reduce({args[0]}, {obj})'
        return obj

    def _emit_array_find(self, obj: str, args: list[str], raw_args=None) -> str:
        if raw_args and len(raw_args) == 1:
            cond = self._inline_predicate(raw_args[0], 'x')
            if cond:
                return f'next((x for x in {obj} if {cond}), None)'
        if args:
            return f'next((x for x in {obj} if {args[0]}(x)), None)'
        return f'next(iter({obj}), None)'

    def _emit_array_find_index(self, obj: str, args: list[str], raw_args=None) -> str:
        if raw_args and len(raw_args) == 1:
            cond = self._inline_predicate(raw_args[0], 'x')
            if cond:
                return f'next((i for i, x in enumerate({obj}) if {cond}), -1)'
        if args:
            return f'next((i for i, x in enumerate({obj}) if {args[0]}(x)), -1)'
        return '-1'

    def _inline_predicate(self, fn_node, var: str) -> str | None:
        """Try to inline an arrow function as a predicate expression.

        Handles: ({ prop }) => prop  ->  x.get('prop')
                 (x) => x.kind === 'SELL'  ->  x.get('kind') == 'SELL'
                 ({ prop }) => { return prop; }  ->  x.get('prop')
        """
        if _type(fn_node) not in ('ArrowFunctionExpression',
                                   'FunctionExpression'):
            return None

        params = _get(fn_node, 'params', [])
        body = _get(fn_node, 'body')
        param_names, destructured_props = _extract_param_info(params)

        # Unwrap single-return block bodies
        if _type(body) == 'BlockStatement':
            stmts = _get(body, 'body', [])
            if len(stmts) == 1 and _type(stmts[0]) == 'ReturnStatement':
                body = stmts[0].argument
            else:
                return None

        # Simple destructured: ({ prop }) => prop
        if (len(destructured_props) == 1
                and _type(body) == 'Identifier'
                and _name(body) == destructured_props[0]):
            return f"{var}.get('{destructured_props[0]}')"

        # Destructured with expression
        if destructured_props:
            subs = {p: f"{var}.get('{p}')" for p in destructured_props}
            return self._expr_with_substitution(body, subs)

        # Simple param: (item) => item.prop === 'value'
        if len(param_names) == 1:
            return self._expr_with_substitution(
                body, {param_names[0]: var})

        return None

    def _inline_transform(self, fn_node, var: str) -> str | None:
        """Try to inline an arrow/function as a map transform expression."""
        return self._inline_predicate(fn_node, var)  # Same logic

    def _expr_with_substitution(self, node, subs: dict[str, str]) -> str | None:
        """Emit an expression, substituting identifiers per the subs dict."""
        if node is None:
            return None
        # Save and restore: we temporarily modify how Identifiers are emitted
        old_subs = getattr(self, '_subs', {})
        self._subs = subs
        try:
            result = self._expr(node)
            return result
        finally:
            self._subs = old_subs

    # --- Patterns (destructuring) ---

    def _emit_params(self, params: list) -> str:
        parts = []
        for p in params:
            parts.append(self._emit_pattern(p))
        return ', '.join(parts)

    def _emit_pattern(self, node) -> str:
        ntype = _type(node)
        if ntype == 'Identifier':
            return _name(node)
        if ntype == 'AssignmentPattern':
            left = self._emit_pattern(node.left)
            right = self._expr(node.right)
            return f'{left}={right}'
        if ntype == 'ObjectPattern':
            props = []
            for prop in node.properties:
                if _type(prop) == 'RestElement':
                    props.append(f'**{self._emit_pattern(prop.argument)}')
                else:
                    props.append(self._emit_pattern(prop.value))
            return ', '.join(props)
        if ntype == 'ArrayPattern':
            elems = []
            for elem in node.elements:
                if elem is None:
                    elems.append('_')
                elif _type(elem) == 'RestElement':
                    elems.append(f'*{self._emit_pattern(elem.argument)}')
                else:
                    elems.append(self._emit_pattern(elem))
            return ', '.join(elems)
        if ntype == 'RestElement':
            return f'*{self._emit_pattern(node.argument)}'
        if ntype == 'MemberExpression':
            return self._emit_MemberExpression(node)

        return _name(node) if hasattr(node, 'name') else 'unknown'

    # --- Helpers ---

    def _emit_block(self, node):
        if _type(node) == 'BlockStatement':
            stmts = _get(node, 'body', [])
            if not stmts:
                self._write('pass')
            for stmt in stmts:
                result = self._emit_node(stmt)
                if isinstance(result, str) and result:
                    self._write(result)
        else:
            result = self._emit_node(node)
            if isinstance(result, str) and result:
                self._write(result)


# --- Utility functions ---

def _type(node) -> str:
    if node is None:
        return 'None'
    if hasattr(node, 'type'):
        return node.type
    if isinstance(node, dict):
        return node.get('type', 'Unknown')
    return type(node).__name__


def _name(node) -> str:
    if node is None:
        return ''
    if isinstance(node, str):
        return node
    if hasattr(node, 'name'):
        return node.name
    if hasattr(node, 'value'):
        return str(node.value)
    return ''


def _get(node, attr: str, default=None):
    if hasattr(node, attr):
        return getattr(node, attr)
    if isinstance(node, dict):
        return node.get(attr, default)
    return default


def _extract_param_info(params) -> tuple[list[str], list[str]]:
    """Extract parameter names and destructured props from param list."""
    param_names = []
    destructured_props = []
    for p in params:
        pt = _type(p)
        if pt == 'Identifier':
            param_names.append(_name(p))
        elif pt == 'ObjectPattern':
            for prop in p.properties:
                pn = _name(prop.key) if hasattr(prop, 'key') else _name(prop.value)
                destructured_props.append(pn)
    return param_names, destructured_props


def _to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    if not name:
        return name
    result = []
    for i, c in enumerate(name):
        if c.isupper():
            if i > 0 and not name[i - 1].isupper():
                result.append('_')
            elif i > 0 and i < len(name) - 1 and name[i - 1].isupper() and not name[i + 1].isupper():
                result.append('_')
            result.append(c.lower())
        else:
            result.append(c)
    return ''.join(result)
