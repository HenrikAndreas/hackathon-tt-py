"""Parse TypeScript files using tree-sitter."""
from __future__ import annotations

import tree_sitter_typescript as ts_typescript
from tree_sitter import Language, Parser

TS_LANGUAGE = Language(ts_typescript.language_typescript())


def parse(source: str | bytes):
    """Parse TypeScript source and return (tree, source_bytes)."""
    parser = Parser(TS_LANGUAGE)
    if isinstance(source, str):
        source = source.encode("utf-8")
    return parser.parse(source), source


def text(node, source: bytes) -> str:
    """Extract source text for a node."""
    return source[node.start_byte : node.end_byte].decode("utf-8")


def child_by_type(node, type_name: str):
    """Get first child of a specific type."""
    for c in node.children:
        if c.type == type_name:
            return c
    return None


def children_by_type(node, type_name: str):
    """Get all children of a specific type."""
    return [c for c in node.children if c.type == type_name]


def child_by_field(node, field_name: str):
    """Get child by field name."""
    return node.child_by_field_name(field_name)


def walk_tree(node, visitor_fn, depth=0):
    """Walk tree and call visitor_fn(node, depth) for each node."""
    visitor_fn(node, depth)
    for child in node.children:
        walk_tree(child, visitor_fn, depth + 1)
