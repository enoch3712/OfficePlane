from officeplane.events.jsonlogic_eval import apply


def test_equality():
    assert apply({"==": [{"var": "a"}, 1]}, {"a": 1}) is True
    assert apply({"==": [{"var": "a"}, 1]}, {"a": 2}) is False


def test_and_or():
    rule = {"and": [{"==": [{"var": "x"}, 1]}, {"==": [{"var": "y"}, 2]}]}
    assert apply(rule, {"x": 1, "y": 2}) is True
    assert apply(rule, {"x": 1, "y": 3}) is False
    rule_or = {"or": [{"==": [{"var": "x"}, 9]}, {"==": [{"var": "y"}, 2]}]}
    assert apply(rule_or, {"x": 1, "y": 2}) is True


def test_in_array():
    rule = {"in": ["monthly", {"var": "tags"}]}
    assert apply(rule, {"tags": ["monthly", "finance"]}) is True
    assert apply(rule, {"tags": ["other"]}) is False


def test_in_string():
    rule = {"in": ["bp", {"var": "title"}]}
    assert apply(rule, {"title": "bp protocol"}) is True


def test_negation():
    assert apply({"!": [{"==": [{"var": "x"}, 1]}]}, {"x": 2}) is True


def test_dotted_var_lookup():
    rule = {"==": [{"var": "document.source_format"}, "pdf"]}
    assert apply(rule, {"document": {"source_format": "pdf"}}) is True


def test_missing_key_returns_default():
    rule = {"==": [{"var": "no.such.key"}, "anything"]}
    assert apply(rule, {}) is False


def test_numeric_comparisons():
    assert apply({">": [{"var": "n"}, 5]}, {"n": 10}) is True
    assert apply({"<=": [{"var": "n"}, 5]}, {"n": 5}) is True


def test_compound_real_world_filter():
    """Match: pdf document with the 'monthly-report' tag."""
    rule = {"and": [
        {"==": [{"var": "document.source_format"}, "pdf"]},
        {"in": ["monthly-report", {"var": "document.tags"}]},
    ]}
    yes = {"document": {"source_format": "pdf", "tags": ["monthly-report", "finance"]}}
    no_format = {"document": {"source_format": "docx", "tags": ["monthly-report"]}}
    no_tag = {"document": {"source_format": "pdf", "tags": ["other"]}}
    assert apply(rule, yes) is True
    assert apply(rule, no_format) is False
    assert apply(rule, no_tag) is False
