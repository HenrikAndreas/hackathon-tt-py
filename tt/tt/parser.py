"""Parse TypeScript files into AST using esprima.

Preprocesses TS source to strip type-only syntax, then parses
the resulting ES6 JavaScript with esprima.
"""
from __future__ import annotations

from pathlib import Path

import esprima

from tt.ts_preprocess import preprocess


def parse_ts_source(source: str) -> esprima.nodes.Module:
    """Parse TypeScript source string into an AST."""
    js_source = preprocess(source)
    try:
        return esprima.parseScript(js_source, tolerant=True)
    except esprima.Error as e:
        # Try module mode if script mode fails
        try:
            return esprima.parseModule(js_source, tolerant=True)
        except esprima.Error:
            raise RuntimeError(f"Failed to parse source: {e}") from e


def parse_ts_file(path: Path) -> esprima.nodes.Module:
    """Parse a TypeScript file into an AST."""
    source = path.read_text(encoding='utf-8')
    return parse_ts_source(source)
