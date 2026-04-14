"""Strip TypeScript-specific syntax to produce parseable ES6 JavaScript.

This module uses Python regex to remove type annotations, interfaces,
enums, generics, access modifiers, and other TS-only constructs so
that the result can be fed to esprima (an ES6 parser).
"""
from __future__ import annotations

import re


def preprocess(source: str) -> str:
    """Convert TypeScript source to parseable ES6 JavaScript."""
    out = source

    # Remove import statements entirely (we resolve imports separately)
    # Handle multiline imports: import { ... } from '...'
    out = re.sub(r'import\s*\{[^}]*\}\s*from\s*[\'"][^\'"]*[\'"];?', '', out, flags=re.DOTALL)
    out = re.sub(r'import\s+\*\s+as\s+\w+\s+from\s*[\'"][^\'"]*[\'"];?', '', out)
    out = re.sub(r'import\s+\w+\s+from\s*[\'"][^\'"]*[\'"];?', '', out)
    out = re.sub(r'^import\s+.*?;\s*$', '', out, flags=re.MULTILINE)

    # Remove export keyword (keep the declaration)
    out = re.sub(r'\bexport\s+(?=class|function|const|let|var|abstract|enum)', '', out)
    out = re.sub(r'^export\s+\{[^}]*\}\s*;?\s*$', '', out, flags=re.MULTILINE)
    out = re.sub(r'^export\s+\*\s+from\s+.*?;?\s*$', '', out, flags=re.MULTILINE)
    out = re.sub(r'^export\s+default\s+', '', out, flags=re.MULTILINE)

    # Remove interface declarations (entire block)
    out = _remove_block(out, r'(?:export\s+)?interface\s+\w+(?:\s+extends\s+[\w,\s<>]+)?\s*\{')

    # Remove type alias declarations
    out = re.sub(r'^(?:export\s+)?type\s+\w+(?:<[^>]*>)?\s*=\s*[^;]+;', '', out, flags=re.MULTILINE)

    # Remove enum declarations - convert to simple objects
    out = _convert_enums(out)

    # Remove decorators (@Something(...))
    out = re.sub(r'@\w+(?:\([^)]*\))?\s*\n?', '', out)

    # Strip access modifiers
    out = re.sub(r'\b(public|private|protected)\s+(?=static|readonly|abstract|async|constructor|get\s|set\s|\w+\s*[\(:<]|\w+\s*=)', '', out)
    out = re.sub(r'\breadonly\s+', '', out)
    out = re.sub(r'\babstract\s+(?=class)', '', out)

    # Remove abstract method declarations (no body)
    out = re.sub(r'^\s*abstract\s+\w+\s*\([^)]*\)\s*:?\s*[^;{]*;\s*$', '', out, flags=re.MULTILINE)

    # Remove optional parameter markers: param? -> param (BEFORE type stripping)
    out = re.sub(r'(\w)\?(?=\s*[,:)\]}=])', r'\1', out)

    # Strip type annotations from parameters and variables
    out = _strip_type_annotations(out)

    # Remove 'as const' and other type assertions
    out = re.sub(r'\s+as\s+const\b', '', out)
    out = re.sub(r'\s+as\s+\w+(?:<[^>]*>)?(?:\[\])?', '', out)

    # Remove generic type parameters from class/function declarations
    # Require identifier immediately before < to avoid matching comparison operators
    out = re.sub(r'(?<=\w)(<(?:[^<>]|<[^>]*>)*>)\s*(?=[\(\{,\)])', '', out)

    # Remove implements clauses
    out = re.sub(r'\s+implements\s+[\w,\s<>]+(?=\s*\{)', '', out)

    # Handle optional chaining: obj?.prop -> (obj != null ? obj.prop : undefined)
    # For now, just convert ?. to . (simpler, handles most cases)
    out = re.sub(r'\?\.\[', '[', out)  # obj?.[0] -> obj[0]
    out = re.sub(r'\?\.', '.', out)     # obj?.prop -> obj.prop

    # Handle nullish coalescing: a ?? b -> (a !== null && a !== undefined ? a : b)
    # We'll handle this in the emitter since esprima doesn't support ??
    # For now convert to || which is close enough for most cases
    out = re.sub(r'\?\?', '||', out)

    # Remove non-null assertions: x!.prop -> x.prop, x! -> x
    out = re.sub(r'([\w\)\]])!\.', r'\1.', out)
    out = re.sub(r'([\w\)\]])!(?=[,;\)\]\s])', r'\1', out)

    # Remove class field declarations with initializers (ES6 doesn't support them)
    # static ENABLE_LOGGING = false; -> store for later injection into constructor
    # For now, just remove them (we'll handle ENABLE_LOGGING as a constant)
    out = re.sub(r'^\s+static\s+\w+\s*=\s*[^;]+;\s*$', '', out, flags=re.MULTILINE)

    # Remove leftover generic type fragments: word<Type>;
    out = re.sub(r'^\s+\w+<[^>]*>;\s*$', '', out, flags=re.MULTILINE)

    # Clean up leftover [] after param type stripping: positions[] -> positions
    out = re.sub(r'(\w)\[\](?=\s*[,\)\n])', r'\1', out)

    # Strip type from destructured patterns: { a, b }: Type -> { a, b }
    # Both in const declarations (before =) and params (before ) or ,)
    out = re.sub(r'(\})\s*:\s*\w+(?:<[^>]*>)?\s*(?=[=\),])', r'\1 ', out)

    # Fix empty catch blocks: catch {} -> catch(e) {}
    out = re.sub(r'\bcatch\s*\{', 'catch(e) {', out)

    # Clean up empty lines
    out = re.sub(r'\n\s*\n\s*\n+', '\n\n', out)

    return out


def _strip_type_annotations(source: str) -> str:
    """Remove TypeScript type annotations from source code.

    Must be careful to NOT strip object literal key-value colons.
    Only strip in known type-annotation contexts.
    """
    out = source

    # 1. Function/method return types: ): Type {  ->  ) {
    # Use brace-aware stripping for complex return types
    out = _strip_return_types(out)

    # 2. Variable type annotations: let x: Type = ...  ->  let x = ...
    # Use brace/paren-aware stripping for complex types
    out = _strip_var_type_annotations(out)

    # 3. Destructured parameter type annotations: }: { ... } & Foo) -> })
    # These can be deeply nested, so use brace matching
    out = _strip_destructured_param_types(out)

    # 4. Simple parameter types in function params
    # Match param: Type patterns inside parenthesized parameter lists
    # We do this by finding function-like param lists and stripping types within
    out = _strip_param_types_in_functions(out)

    # 5. Class field declarations (type only, no initializer): fieldName: Type;
    # Use [^\S\n] instead of \s to avoid spanning newlines
    out = re.sub(r'^([^\S\n]*)\w+\s*:\s*[\w\[\]|&<>,[^\S\n].{}()\'"]+;\s*$', '', out, flags=re.MULTILINE)

    # 5b. Bare field declarations (after type stripping): `fieldName;` or `fieldName[];` in class body
    # Only at class-level indentation (2-4 spaces), not deep in method bodies
    out = re.sub(r'^( {2,4})\w+(?:\[\])?;\s*$', '', out, flags=re.MULTILINE)

    # 6. Generic type parameters in new/call: new Map<string, string>() -> new Map()
    out = re.sub(r'(new\s+\w+)<[^>]*>', r'\1', out)
    out = re.sub(r'(\w+(?:\.\w+)*)<[^>]*>\(', r'\1(', out)

    return out


def _strip_param_types_in_functions(source: str) -> str:
    """Strip type annotations from function/method parameter lists.

    Strategy: find param-like `: TypeName` patterns where TypeName starts
    with an uppercase letter or is a known primitive/array type.
    These only appear in type annotation contexts, not object literals
    (where values follow the colon, not type names).
    """
    # Match word: TypeName where TypeName is a TS type (uppercase or primitive)
    type_pattern = (
        r'(\w+)\s*:\s*'
        r'(?:string|number|boolean|void|any|never|null|undefined|object'
        r'|Big|Date|Promise'
        r'|[A-Z]\w*)'
        r'(?:\[\])*'
        r'(?:\s*\|\s*(?:string|number|boolean|null|undefined|[A-Z]\w*)(?:\[\])*)*'
        # Must be followed by word boundary, then NOT . (values use . for member access)
        r'\b(?![\.\w])'
    )
    out = re.sub(type_pattern, r'\1', source)
    return out


def _strip_return_types(source: str) -> str:
    """Strip return type annotations from function/method declarations.

    Handles: ): Type { and ): { complex: Type }[] {
    Converts to: ) {

    Strategy: find the LAST `{` on the line that's at brace-depth 0.
    Everything between ): and that { is the return type.
    """
    result = []
    for line in source.split('\n'):
        # Find `) :` pattern (closing paren + colon = return type start)
        m = re.search(r'\)\s*:\s*', line)
        if m:
            after_colon = line[m.end():]
            # Find the last { at depth 0 — that's the method body opener
            depth_brace = 0
            last_zero_brace = -1
            for i, c in enumerate(after_colon):
                if c == '{':
                    if depth_brace == 0:
                        last_zero_brace = i
                    depth_brace += 1
                elif c == '}':
                    depth_brace -= 1

            if last_zero_brace >= 0 and depth_brace > 0:
                # The last { at depth 0 is the body start
                line = line[:m.start()] + ') ' + after_colon[last_zero_brace:]
        result.append(line)
    return '\n'.join(result)


def _strip_var_type_annotations(source: str) -> str:
    """Strip type annotations from variable declarations.

    Handles all forms:
      const x: Type = value
      const x: { [key: string]: Big } = {}
      const x: (Type & { field: boolean })[] = []
      let x: Type;
    """
    result = []
    # Process line by line, with awareness of multi-line declarations
    lines = source.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this line has a variable declaration with type annotation
        m = re.match(r'^(\s*(?:let|const|var)\s+\w+)\s*:\s*', line)
        if m:
            prefix = m.group(1)
            rest_of_line = line[m.end():]
            # Find where the type ends and the value/semicolon begins
            # Scan forward, tracking braces/parens/angles
            full_text = rest_of_line
            line_idx = i
            while line_idx < len(lines) - 1:
                # Check if we can find = or ; at top-level (no unclosed brackets)
                pos = _find_type_end(full_text)
                if pos is not None:
                    # Found the end of the type annotation
                    result.append(prefix + full_text[pos:])
                    # Skip any consumed continuation lines
                    i = line_idx + 1
                    break
                # Need more lines
                line_idx += 1
                full_text += '\n' + lines[line_idx]
            else:
                result.append(line)
                i += 1
        else:
            result.append(line)
            i += 1
    return '\n'.join(result)


def _find_type_end(text: str) -> int | None:
    """Find where a type annotation ends in text (position of = or ;).

    Returns the position of the `=` or `;` that follows the type,
    or None if the type doesn't end in this text.
    """
    depth_brace = 0
    depth_paren = 0
    depth_angle = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c == '{':
            depth_brace += 1
        elif c == '}':
            depth_brace -= 1
        elif c == '(':
            depth_paren += 1
        elif c == ')':
            depth_paren -= 1
        elif c == '<':
            depth_angle += 1
        elif c == '>' and depth_angle > 0:
            depth_angle -= 1
        elif c in ('=', ';') and depth_brace == 0 and depth_paren == 0 and depth_angle == 0:
            # Skip trailing [] before = or ;
            return i
        i += 1
    return None


def _strip_destructured_param_types(source: str) -> str:
    """Strip type annotations from destructured parameters.

    Handles patterns like:
        ({ a, b }: { a: Type; b: Type } & Foo): ReturnType {
    Converts to:
        ({ a, b }): ReturnType {
    Uses brace matching for nested type blocks.
    """
    result = source
    while True:
        # Find `}: {` pattern (end of destructured param, start of type block)
        m = re.search(r'\}\s*:\s*\{', result)
        if not m:
            break

        # Check if this is inside a parameter context
        # (simplification: just strip it)
        type_start = m.start() + 1  # After the }
        brace_start = result.index('{', type_start)

        # Find matching closing brace
        depth = 0
        i = brace_start
        while i < len(result):
            if result[i] == '{':
                depth += 1
            elif result[i] == '}':
                depth -= 1
                if depth == 0:
                    # Remove everything from after } to after the matching }
                    # Also remove any trailing ` & TypeName` patterns
                    end = i + 1
                    rest = result[end:]
                    # Strip trailing intersection types: & TypeName
                    stripped = re.match(r'(\s*&\s*\w+(?:<[^>]*>)?)*', rest)
                    if stripped:
                        end += stripped.end()
                    result = result[:type_start] + result[end:]
                    break
            i += 1
        else:
            break  # No matching brace
    return result


def _remove_block(source: str, pattern: str) -> str:
    """Remove a block (with balanced braces) matching the pattern."""
    result = source
    while True:
        m = re.search(pattern, result)
        if not m:
            break
        start = m.start()
        # Find matching closing brace
        depth = 0
        i = m.end() - 1  # Start from the opening brace
        while i < len(result):
            if result[i] == '{':
                depth += 1
            elif result[i] == '}':
                depth -= 1
                if depth == 0:
                    result = result[:start] + result[i + 1:]
                    break
            i += 1
        else:
            break  # Safety: no matching brace found
    return result


def _convert_enums(source: str) -> str:
    """Convert TypeScript enums to JavaScript objects."""
    def replace_enum(m):
        name = m.group(1)
        body = m.group(2)
        # Parse enum members
        members = []
        for member_match in re.finditer(r"(\w+)\s*=\s*['\"]([^'\"]*)['\"]", body):
            members.append(f"  {member_match.group(1)}: '{member_match.group(2)}'")
        if not members:
            # Numeric enum
            for i, member_match in enumerate(re.finditer(r'(\w+)', body)):
                members.append(f"  {member_match.group(1)}: {i}")
        return f"const {name} = {{\n" + ",\n".join(members) + "\n};"

    return re.sub(
        r'(?:export\s+)?enum\s+(\w+)\s*\{([^}]*)\}',
        replace_enum,
        source
    )
