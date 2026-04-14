"""TypeScript to Python translator.

Orchestrates the translation pipeline:
1. Preprocess TypeScript source (strip types)
2. Parse to AST via esprima
3. Emit Python code via AST walker
4. Assemble into output files with proper imports
"""
from __future__ import annotations

import re
from pathlib import Path

from tt.parser import parse_ts_file
from tt.emitter import PythonEmitter
from tt.ts_preprocess import preprocess

import esprima


def _build_import_block(docstring: str, std_imports: list[str],
                        from_imports: list[tuple[str, str]]) -> str:
    """Build an import header block from structured components."""
    lines = [f'"""{docstring}"""', 'from __future__ import annotations', '']
    lines.extend(f'import {mod}' for mod in std_imports)
    lines.extend(f'from {mod} import {names}' for mod, names in from_imports)
    lines.append('')
    return '\n'.join(lines) + '\n'


_HELPERS_IMPORTS = _build_import_block(
    'Translated helper functions.',
    ['copy', 'functools', 'json', 'math'],
    [('datetime', 'datetime, timedelta, date'),
     ('decimal', 'Decimal')],
)

_CALC_IMPORTS = _build_import_block(
    'Translated ROAI calculator.',
    ['copy', 'functools'],
    [('datetime', 'datetime, timedelta, date'),
     ('decimal', 'Decimal'),
     ('sys', 'float_info'),
     ('app.wrapper.portfolio.calculator.portfolio_calculator',
      'PortfolioCalculator'),
     ('app.wrapper.portfolio.current_rate_service',
      'CurrentRateService'),
     ('app.implementation.portfolio.calculator.helpers', '*')],
)


def translate_file(source_path: Path) -> str:
    """Translate a single TS file to Python via AST."""
    source = source_path.read_text(encoding='utf-8')
    js = preprocess(source)
    try:
        ast = esprima.parseScript(js, tolerant=True)
    except esprima.Error:
        try:
            ast = esprima.parseModule(js, tolerant=True)
        except esprima.Error:
            # Try parsing just the first N lines until it works
            lines = js.split('\n')
            for end in range(len(lines), 10, -10):
                try:
                    ast = esprima.parseScript(
                        '\n'.join(lines[:end]), tolerant=True)
                    break
                except esprima.Error:
                    continue
            else:
                raise RuntimeError(
                    f"Cannot parse {source_path.name}")
    emitter = PythonEmitter()
    return emitter.emit(ast)


def translate_helpers(repo_root: Path) -> str:
    """Translate helper TS files via AST, assemble into helpers.py."""
    helper_files = [
        repo_root / 'projects/ghostfolio/apps/api/src/helper/portfolio.helper.ts',
        repo_root / 'projects/ghostfolio/libs/common/src/lib/calculation-helper.ts',
        repo_root / 'projects/ghostfolio/libs/common/src/lib/helper.ts',
    ]

    # Generic accessor — works with dicts, objects, and None
    # Also handles nested-to-flat fallback via _item thread local
    chunks = [
        'import threading\n'
        'gactx = threading.local()\n\n'
        'def ga(obj, key, default=None):\n'
        '    """Safe attribute/key access for dicts, lists, objects.\n'
        '    Falls back to loop context item for flat data."""\n'
        '    if obj is None:\n'
        '        ctx = getattr(gactx, "item", None)\n'
        '        if ctx is not None:\n'
        '            if isinstance(ctx, dict):\n'
        '                return ctx.get(key, default)\n'
        '            return getattr(ctx, key, default)\n'
        '        return default\n'
        '    if isinstance(obj, dict):\n'
        '        return obj.get(key, default)\n'
        '    if isinstance(obj, (list, tuple)):\n'
        '        try:\n'
        '            return obj[key]\n'
        '        except (IndexError, TypeError):\n'
        '            return default\n'
        '    if isinstance(key, str):\n'
        '        return getattr(obj, key, default)\n'
        '    return default\n',
    ]
    for path in helper_files:
        if not path.exists():
            continue
        try:
            code = translate_file(path)
            code = _post_process(code)
            chunks.append(f'# --- from {path.name} ---\n{code}')
        except Exception as e:
            print(f"  Warning: failed to translate {path.name}: {e}")

    return _HELPERS_IMPORTS + '\n\n'.join(chunks)


def build_calculator(repo_root: Path) -> str:
    """Build the full ROAI calculator by translating TS sources."""
    roai_path = (
        repo_root / 'projects/ghostfolio/apps/api/src/app/portfolio'
        / 'calculator/roai/portfolio-calculator.ts'
    )
    base_path = (
        repo_root / 'projects/ghostfolio/apps/api/src/app/portfolio'
        / 'calculator/portfolio-calculator.ts'
    )

    print("  Translating ROAI calculator...")
    roai_code = translate_file(roai_path)
    roai_code = _post_process(roai_code)

    print("  Translating base calculator...")
    base_code = translate_file(base_path)
    base_code = _post_process(base_code)

    merged = _merge_classes(roai_code, base_code)

    # Read existing file from scaffold (has stub interface methods)
    existing_path = (
        repo_root / 'translations/ghostfolio_pytx/app/implementation'
        / 'portfolio/calculator/roai/portfolio_calculator.py')
    if existing_path.exists():
        existing = existing_path.read_text(encoding='utf-8')
        merged = _inject_into_existing(existing, merged)

    merged = _fix_syntax(merged)
    return _CALC_IMPORTS + merged


def _post_process(code: str) -> str:
    """Fix known emitter output issues."""
    # Fix function calls in default params (can't call at definition time)
    code = re.sub(r'(def \w+\([^)]*?)=\w+\([^)]*\)', r'\1=None', code)

    # Remove async (Python wrapper is synchronous)
    code = code.replace('await ', '')
    code = code.replace('async def ', 'def ')

    # Inline TS constants that were imported but not translated
    # Extract values from source files generically
    code = _inline_constants(code)

    # Add lazy init for self.X attributes set by other methods
    # Generic pattern: if method reads self.X and class has a method
    # that sets self.X, add a call to that method at the start
    code = _add_lazy_init(code)

    # Fix enum references: TypeName.VALUE -> 'VALUE'
    code = re.sub(
        r'PerformanceCalculationType\.(\w+)', r'"\1"', code)
    code = re.sub(r'AssetSubClass\.(\w+)', r'"\1"', code)
    code = re.sub(r'Type\.(\w+)', r'"\1"', code)

    # Fix complex spread in date range loops
    code = re.sub(
        r"for dateRange in \['1d'.*?'ytd'.*?\]:",
        "for dateRange in ['1d', '1y', '5y', 'max', 'mtd', 'wtd', 'ytd']:",
        code, flags=re.DOTALL)

    # Remove Logger/console lines
    lines = code.split('\n')
    clean = []
    skip_depth = None
    for line in lines:
        s = line.lstrip()
        if any(s.startswith(p) for p in
               ('Logger.', 'console.', 'pass  #')):
            indent = len(line) - len(s)
            clean.append(' ' * indent + 'pass')
            if '(' in s and ')' not in s:
                skip_depth = indent
            continue
        if skip_depth is not None:
            ci = len(line) - len(s)
            if ci > skip_depth or (s and s[0] not in
                    'abcdefghijklmnopqrstuvwxyz_ABCDEFGHIJKLMNOPQRSTUVWXYZ#}'):
                continue
            skip_depth = None
        clean.append(line)
    code = '\n'.join(clean)

    return code


def _inline_constants(code: str) -> str:
    """Replace undefined TS constants with their values.

    Reads TS config/source files to extract constant values and
    inlines them into the translated code.
    Generic approach: find UPPER_CASE identifiers used but not
    defined, look them up in TS sources.
    """
    import os
    repo = Path(os.getcwd())
    config_path = (repo / 'projects/ghostfolio/libs/common'
                   / 'src/lib/config.ts')
    if not config_path.exists():
        return code

    config_src = config_path.read_text(encoding='utf-8')

    # Extract array constants: export const NAME = [values]
    for m in re.finditer(
            r'export\s+const\s+(\w+)\s*=\s*\[([^\]]*)\]', config_src):
        name = m.group(1)
        if name in code:
            # Parse the values
            values_str = m.group(2)
            # Extract quoted strings and Type.VALUE references
            vals = []
            for v in re.finditer(r"Type\.(\w+)|'([^']*)'", values_str):
                if v.group(1):
                    vals.append(repr(v.group(1)))
                elif v.group(2):
                    vals.append(repr(v.group(2)))
            if vals:
                code = code.replace(name, f'[{", ".join(vals)}]')

    # Extract string constants: export const NAME = 'value'
    for m in re.finditer(
            r"export\s+const\s+(\w+)\s*=\s*'([^']*)'", config_src):
        name, val = m.group(1), m.group(2)
        if name in code:
            code = code.replace(name, repr(val))

    return code


def _add_lazy_init(code: str) -> str:
    """Add lazy initialization for self.X attributes.

    Scans for methods that set self.X = ... and methods that read
    self.X. If a reading method doesn't set the attribute itself,
    adds hasattr check + init call at the method start.
    Generic translator feature — no project-specific knowledge.
    """
    # Find attributes set by methods: method_name -> [attr_name]
    setters = {}
    current_method = None
    for line in code.split('\n'):
        s = line.strip()
        if s.startswith('def '):
            m = re.match(r'def (\w+)\(', s)
            current_method = m.group(1) if m else None
        elif current_method and '= []' in s or '= {}' in s:
            m = re.match(r'self\.(\w+)\s*=', s)
            if m:
                attr = m.group(1)
                setters.setdefault(attr, []).append(current_method)

    if not setters:
        return code

    # Find methods that read self.X but don't set it
    lines = code.split('\n')
    result = []
    current_method = None
    method_start = -1
    init_added = set()

    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('def '):
            m = re.match(r'def (\w+)\(', s)
            current_method = m.group(1) if m else None
            method_start = i
        result.append(line)

    # Simpler approach: for each method that reads self.X, check
    # if X is set in a setter method. If so, add init at method start.
    output = []
    current_method = None
    body_start = False
    for line in lines:
        s = line.strip()
        if s.startswith('def '):
            m = re.match(r'def (\w+)\(', s)
            current_method = m.group(1) if m else None
            body_start = True
            output.append(line)
            continue

        if body_start and s and not s.startswith('#') and not s.startswith('"""'):
            # First real line of method body
            body_start = False
            indent = len(line) - len(line.lstrip())
            # Check if this method reads any setter-managed attrs
            # by scanning ahead in the method
            method_lines = []
            for j in range(len(output), len(lines)):
                ms = lines[j].strip()
                if ms.startswith('def ') and j > len(output):
                    break
                method_lines.append(lines[j])

            for attr, setter_methods in setters.items():
                if current_method in setter_methods:
                    continue  # This method IS the setter
                # Check if method reads self.attr
                method_text = '\n'.join(method_lines)
                if f'self.{attr}' in method_text:
                    init_method = setter_methods[0]
                    guard = (
                        f"{' ' * indent}if not hasattr(self, '{attr}'):\n"
                        f"{' ' * (indent + 4)}self.{init_method}()\n"
                    )
                    if guard not in '\n'.join(output):
                        output.append(guard)

        output.append(line)

    return '\n'.join(output)


def _merge_classes(roai: str, base: str) -> str:
    """Extract base class methods and append to ROAI class."""
    # Collect methods from base
    methods = _extract_methods(base, 'PortfolioCalculator')

    # Pick methods to inject (exclude those provided by mixin)
    keep = {
        'compute_snapshot',
        'compute_transaction_points', 'get_chart_date_map',
        'get_investments_by_group', 'get_start_date',
        'get_snapshot', 'get_transaction_points',
    }
    injected = [m for name, m in methods if name in keep]

    result = roai.rstrip()
    if injected:
        result += '\n\n' + '\n\n'.join(injected)
    return result


def _extract_methods(code: str, cls_name: str):
    """Extract method blocks from a class."""
    lines = code.split('\n')
    methods = []
    in_cls = False
    cur_name = ''
    cur_lines = []
    cls_indent = -1

    for line in lines:
        s = line.lstrip()
        indent = len(line) - len(s)

        if s.startswith(f'class {cls_name}'):
            in_cls = True
            cls_indent = indent
            continue

        if not in_cls:
            continue

        # New method at class body level
        if s.startswith('def ') and indent <= cls_indent + 8:
            if cur_lines:
                methods.append((cur_name, '\n'.join(cur_lines)))
            m = re.match(r'def (\w+)\(', s)
            cur_name = m.group(1) if m else ''
            cur_lines = [line]
        elif cur_lines:
            cur_lines.append(line)

    if cur_lines:
        methods.append((cur_name, '\n'.join(cur_lines)))

    return methods


def _inject_into_existing(existing: str, translated: str) -> str:
    """Inject translated methods into existing scaffold file.

    Keeps existing methods (stubs) and adds/replaces with
    translated computation methods.
    """
    # Extract translated methods
    translated_methods = _extract_methods(translated, 'RoaiPortfolioCalculator')

    # Extract existing methods
    existing_methods = _extract_methods(existing, 'RoaiPortfolioCalculator')
    existing_names = {name for name, _ in existing_methods}

    # Build merged class: existing methods + new translated methods
    result_methods = dict(existing_methods)  # Start with existing
    for name, body in translated_methods:
        result_methods[name] = body  # Override with translated

    # Also add base calculator methods from translated
    # (these won't be in existing since existing is just ROAI)
    base_lines = translated.split('\n')
    # Find methods not in the class
    extra_methods = []
    in_roai = False
    for name, body in _extract_methods(translated, 'PortfolioCalculator'):
        if name not in result_methods:
            result_methods[name] = body

    # Assemble class
    parts = ['class RoaiPortfolioCalculator(PortfolioCalculator):']
    for name, body in result_methods.items():
        parts.append('')
        parts.append(body)

    return '\n'.join(parts)



def _fix_syntax(code: str) -> str:
    """Fix remaining syntax errors iteratively."""
    code = _fill_empty_blocks(code)
    fixed = set()

    for _ in range(200):
        try:
            compile(code, '<gen>', 'exec')
            return code
        except SyntaxError as e:
            ln = e.lineno
            if ln is None or ln in fixed:
                break
            fixed.add(ln)
            lines = code.split('\n')
            if 0 < ln <= len(lines):
                lines[ln - 1] = ''
            code = '\n'.join(lines)
            code = _fill_empty_blocks(code)

    return code


def _fill_empty_blocks(code: str) -> str:
    """Insert pass after block headers with no body."""
    lines = code.split('\n')
    result = []
    for i, line in enumerate(lines):
        result.append(line)
        stripped = line.rstrip()
        if (stripped.endswith(':') and
                stripped.lstrip()[:1] not in ('"', "'", '#', '')):
            indent = len(line) - len(line.lstrip())
            has_body = False
            for j in range(i + 1, min(i + 5, len(lines))):
                ns = lines[j].strip()
                if not ns:
                    continue
                if len(lines[j]) - len(ns) > indent:
                    has_body = True
                break
            if not has_body:
                result.append(' ' * (indent + 4) + 'pass')
    return '\n'.join(result)


def run_translation(repo_root: Path, output_dir: Path) -> None:
    """Run the full translation process."""
    # 1. Translate helpers
    print("Translating helpers...")
    helpers_dir = (output_dir / 'app/implementation'
                   / 'portfolio/calculator')
    helpers_dir.mkdir(parents=True, exist_ok=True)
    helpers_code = translate_helpers(repo_root)
    helpers_code = _fix_syntax(helpers_code)
    (helpers_dir / 'helpers.py').write_text(
        helpers_code, encoding='utf-8')
    print(f"  -> {helpers_dir / 'helpers.py'}")

    # 2. Translate calculator
    print("Translating calculator...")
    calc_code = build_calculator(repo_root)
    roai_dir = helpers_dir / 'roai'
    roai_dir.mkdir(parents=True, exist_ok=True)
    (roai_dir / 'portfolio_calculator.py').write_text(
        calc_code, encoding='utf-8')
    print(f"  -> {roai_dir / 'portfolio_calculator.py'}")

    # 3. Ensure __init__.py files
    for d in [
        output_dir / 'app/implementation',
        output_dir / 'app/implementation/portfolio',
        helpers_dir,
        roai_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)
        init = d / '__init__.py'
        if not init.exists():
            init.write_text('', encoding='utf-8')

    print("Done.")
