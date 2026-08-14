from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Node, Tree

from app.analysis.treesitter_parser import EXTENSION_TO_GRAMMAR, parse_file


@dataclass
class ExtractedSymbol:
    name: str
    kind: str  # "function" | "class" | "method"
    start_line: int  # 1-indexed, inclusive
    end_line: int  # 1-indexed, inclusive


# Node types whose own `name` field gives the symbol's name directly.
# Maps grammar key -> {node_type: kind}.
DIRECT_NAME_NODE_KINDS: dict[str, dict[str, str]] = {
    "python": {
        "function_definition": "function",
        "class_definition": "class",
    },
    "javascript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
    },
    "typescript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "interface_declaration": "class",
    },
    "tsx": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "interface_declaration": "class",
    },
}

# Node types that represent an anonymous function/class expression whose
# name (if any) lives on the *parent* variable_declarator, e.g.:
#   const foo = () => {}          <- arrow_function has no name field
#   const bar = function() {}     <- function_expression has no name field
# Only extracted when the parent is actually a variable_declarator with
# a name — an arrow function passed inline as a callback has no useful
# symbol name and is skipped.
PARENT_NAME_NODE_TYPES: dict[str, set[str]] = {
    "python": set(),  # Python has no anonymous-assigned-to-name equivalent worth extracting
    "javascript": {"arrow_function", "function_expression"},
    "typescript": {"arrow_function", "function_expression"},
    "tsx": {"arrow_function", "function_expression"},
}


def extract_symbols(source: bytes, extension: str) -> list[ExtractedSymbol]:
    """Parses `source` and extracts function/class/method symbols.
    Returns an empty list for unsupported extensions or unparseable
    content — never raises, since one bad file shouldn't fail a whole
    repo's analysis (TASKS.md Phase 3: handle unparsed files gracefully)."""
    grammar = EXTENSION_TO_GRAMMAR.get(extension.lower())
    if grammar is None:
        return []

    from app.analysis.treesitter_parser import parse_source

    tree = parse_source(source, extension)
    if tree is None:
        return []

    return _extract_from_tree(tree, grammar)


def extract_symbols_from_file(path: Path) -> list[ExtractedSymbol]:
    """Same as extract_symbols, but reads + parses directly from disk."""
    grammar = EXTENSION_TO_GRAMMAR.get(path.suffix.lower())
    if grammar is None:
        return []

    tree = parse_file(path)
    if tree is None:
        return []

    return _extract_from_tree(tree, grammar)


def _extract_from_tree(tree: Tree, grammar: str) -> list[ExtractedSymbol]:
    direct_kinds = DIRECT_NAME_NODE_KINDS.get(grammar, {})
    parent_name_types = PARENT_NAME_NODE_TYPES.get(grammar, set())

    symbols: list[ExtractedSymbol] = []
    _walk(tree.root_node, direct_kinds, parent_name_types, symbols)
    return symbols


def _walk(
    node: Node,
    direct_kinds: dict[str, str],
    parent_name_types: set[str],
    out: list[ExtractedSymbol],
) -> None:
    if node.type in direct_kinds:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            kind = direct_kinds[node.type]
            # Python has no distinct "method" node type — a method is just
            # a function_definition whose immediate enclosing block belongs
            # to a class_definition. Reclassify in that case.
            if kind == "function" and node.type == "function_definition" and _is_python_method(node):
                kind = "method"
            out.append(
                ExtractedSymbol(
                    name=name_node.text.decode("utf-8", errors="replace"),
                    kind=kind,
                    start_line=node.start_point.row + 1,
                    end_line=node.end_point.row + 1,
                )
            )
    elif node.type in parent_name_types:
        parent = node.parent
        if parent is not None and parent.type == "variable_declarator":
            name_node = parent.child_by_field_name("name")
            if name_node is not None:
                out.append(
                    ExtractedSymbol(
                        name=name_node.text.decode("utf-8", errors="replace"),
                        kind="function",
                        # Line range covers the function body itself, not
                        # the `const foo = ` prefix, matching direct-name
                        # nodes' convention of spanning the definition.
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                    )
                )

    for child in node.children:
        _walk(child, direct_kinds, parent_name_types, out)


def _is_python_method(function_def_node: Node) -> bool:
    """True if a Python function_definition's immediate parent block
    belongs directly to a class_definition (i.e. it's a method, not a
    nested/local function inside another function)."""
    block = function_def_node.parent
    if block is None or block.type != "block":
        return False
    class_node = block.parent
    return class_node is not None and class_node.type == "class_definition"