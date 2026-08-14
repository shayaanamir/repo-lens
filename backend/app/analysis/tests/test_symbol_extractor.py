from app.analysis.symbol_extractor import extract_symbols


def test_python_top_level_function_and_class():
    src = b"""
class Foo:
    def method_a(self):
        pass

def top_level():
    pass
"""
    symbols = extract_symbols(src, ".py")
    by_name = {s.name: s for s in symbols}

    assert by_name["Foo"].kind == "class"
    assert by_name["method_a"].kind == "method"
    assert by_name["top_level"].kind == "function"


def test_python_nested_function_is_not_a_method():
    src = b"""
def outer():
    def inner():
        pass
    return inner
"""
    symbols = extract_symbols(src, ".py")
    by_name = {s.name: s for s in symbols}

    assert by_name["outer"].kind == "function"
    assert by_name["inner"].kind == "function"  # nested in a function, not a class


def test_javascript_class_method_and_function():
    src = b"""
class Foo {
  methodA() {
    return 1;
  }
}

function topLevel() {
  return 2;
}
"""
    symbols = extract_symbols(src, ".js")
    by_name = {s.name: s for s in symbols}

    assert by_name["Foo"].kind == "class"
    assert by_name["methodA"].kind == "method"
    assert by_name["topLevel"].kind == "function"


def test_javascript_arrow_function_assigned_to_const():
    src = b"""
const arrowFn = () => {
  return 1;
};

const anotherArrow = function() {
  return 2;
};
"""
    symbols = extract_symbols(src, ".js")
    names = {s.name for s in symbols}

    assert "arrowFn" in names
    assert "anotherArrow" in names


def test_javascript_anonymous_inline_arrow_is_skipped():
    src = b"[1, 2, 3].map(x => x * 2);"
    symbols = extract_symbols(src, ".js")

    assert symbols == []  # no name to assign, correctly not extracted


def test_typescript_interface_treated_as_class():
    src = b"""
interface Bar {
  x: number;
}
"""
    symbols = extract_symbols(src, ".ts")
    assert symbols[0].name == "Bar"
    assert symbols[0].kind == "class"


def test_tsx_component_functions():
    src = b"""
const MyComponent = () => {
  return <div>hello</div>;
};

function AnotherComponent() {
  return <span>hi</span>;
}
"""
    symbols = extract_symbols(src, ".tsx")
    names = {s.name for s in symbols}

    assert "MyComponent" in names
    assert "AnotherComponent" in names


def test_unsupported_extension_returns_empty_list():
    assert extract_symbols(b"fn main() {}", ".rs") == []