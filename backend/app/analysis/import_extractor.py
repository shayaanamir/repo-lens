from dataclasses import dataclass

from tree_sitter import Node, Tree

from app.analysis.treesitter_parser import EXTENSION_TO_GRAMMAR, parse_source


@dataclass
class ExtractedImport:
    # Raw specifier exactly as written in source, e.g. "./foo", "os.path",
    # "..pkg", "react". Resolution into an actual repo file happens
    # separately in import_resolver.py — this module only extracts.
    specifier: str
    # True for Python "from . import x" / "from .foo import x" (leading
    # dots) and JS/TS "./foo" / "../foo" — i.e. definitely repo-relative,
    # not a third-party package. False otherwise (may still turn out to
    # be in-repo for Python absolute imports, but usually isn't).
    is_relative: bool
    # For Python "from X import a, b, c" only: the imported names. Needed
    # to resolve dots-only specifiers like "from . import sibling", where
    # the module being pointed at is one of these names, not the (empty)
    # module part. Empty for plain "import x" and all JS/TS imports.
    imported_names: tuple[str, ...] = ()


def extract_imports(source: bytes, extension: str) -> list[ExtractedImport]:
    """Extracts raw import specifiers from source. Never raises — returns
    an empty list for unsupported extensions or unparseable content."""
    grammar = EXTENSION_TO_GRAMMAR.get(extension.lower())
    if grammar is None:
        return []

    tree = parse_source(source, extension)
    if tree is None:
        return []

    if grammar == "python":
        return _extract_python_imports(tree)
    return _extract_js_ts_imports(tree)  # javascript, typescript, tsx all share syntax


def _extract_python_imports(tree: Tree) -> list[ExtractedImport]:
    imports: list[ExtractedImport] = []

    def walk(node: Node) -> None:
        if node.type == "import_statement":
            # "import os" / "import os.path" — one or more dotted_name
            # children (comma-separated multi-imports share the node).
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append(ExtractedImport(specifier=child.text.decode(), is_relative=False))
                elif child.type == "aliased_import":
                    dotted = child.child_by_field_name("name") or _first_child_of_type(child, "dotted_name")
                    if dotted is not None:
                        imports.append(ExtractedImport(specifier=dotted.text.decode(), is_relative=False))

        elif node.type == "import_from_statement":
            # "from X import ..." — the module reference is either a
            # dotted_name (absolute, e.g. "from os import path") or a
            # relative_import (leading dots, e.g. "from .foo import bar").
            module_node = None
            for child in node.children:
                if child.type in ("dotted_name", "relative_import"):
                    module_node = child
                    break

            # Names after "import" (skip the module_node itself, which
            # for absolute imports is also a dotted_name and would
            # otherwise be double-counted).
            names: list[str] = []
            for child in node.children:
                if child is module_node:
                    continue
                if child.type == "dotted_name":
                    names.append(child.text.decode())
                elif child.type == "aliased_import":
                    name_child = _first_child_of_type(child, "dotted_name")
                    if name_child is not None:
                        names.append(name_child.text.decode())

            if module_node is not None:
                if module_node.type == "relative_import":
                    imports.append(
                        ExtractedImport(
                            specifier=module_node.text.decode(),
                            is_relative=True,
                            imported_names=tuple(names),
                        )
                    )
                else:
                    imports.append(
                        ExtractedImport(specifier=module_node.text.decode(), is_relative=False)
                    )

        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return imports


def _extract_js_ts_imports(tree: Tree) -> list[ExtractedImport]:
    imports: list[ExtractedImport] = []

    def walk(node: Node) -> None:
        if node.type in ("import_statement", "export_statement"):
            source_node = node.child_by_field_name("source")
            if source_node is not None:
                specifier = _string_node_value(source_node)
                if specifier is not None:
                    imports.append(
                        ExtractedImport(
                            specifier=specifier,
                            is_relative=specifier.startswith("."),
                        )
                    )
        elif node.type == "call_expression":
            callee = node.children[0] if node.children else None
            if callee is not None and callee.type == "identifier" and callee.text == b"require":
                args_node = node.child_by_field_name("arguments")
                if args_node is not None:
                    for arg in args_node.children:
                        if arg.type == "string":
                            specifier = _string_node_value(arg)
                            if specifier is not None:
                                imports.append(
                                    ExtractedImport(
                                        specifier=specifier,
                                        is_relative=specifier.startswith("."),
                                    )
                                )
                            break  # only the first argument to require() is the module path

        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return imports


def _string_node_value(string_node: Node) -> str | None:
    """Pulls the actual text out of a tree-sitter `string` node, i.e. the
    content between the quotes (the string_fragment child)."""
    for child in string_node.children:
        if child.type == "string_fragment":
            return child.text.decode("utf-8", errors="replace")
    return None


def _first_child_of_type(node: Node, node_type: str) -> Node | None:
    for child in node.children:
        if child.type == node_type:
            return child
    return None