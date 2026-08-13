from app.analysis.treesitter_parser import parse_source, get_parser_for_extension


def test_parses_python_source():
    source = b"def foo():\n    pass\n"
    tree = parse_source(source, ".py")

    assert tree is not None
    assert tree.root_node.type == "module"
    assert not tree.root_node.has_error


def test_parses_javascript_source():
    source = b"function foo() { return 1; }\n"
    tree = parse_source(source, ".js")

    assert tree is not None
    assert tree.root_node.type == "program"
    assert not tree.root_node.has_error


def test_parses_typescript_source():
    source = b"function foo(): number { return 1; }\n"
    tree = parse_source(source, ".ts")

    assert tree is not None
    assert not tree.root_node.has_error


def test_parses_tsx_source():
    source = b"const el = <div>hello</div>;\n"
    tree = parse_source(source, ".tsx")

    assert tree is not None
    assert not tree.root_node.has_error


def test_unsupported_extension_returns_none():
    assert get_parser_for_extension(".rs") is None
    assert parse_source(b"fn main() {}", ".rs") is None


def test_malformed_source_still_returns_a_tree():
    # Tree-sitter is error-tolerant by design — it returns a best-effort
    # tree with error nodes rather than raising, which matters for us
    # since we can't guarantee every file in a cloned repo is valid.
    tree = parse_source(b"def foo(:\n", ".py")

    assert tree is not None
    assert tree.root_node.has_error