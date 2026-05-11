from officeplane.orchestration.refs import resolve


def test_simple_parameter_substitution():
    out = resolve(
        {"document_id": "${parameters.source}"},
        parameters={"source": "abc-123"},
        step_outputs={},
    )
    assert out == {"document_id": "abc-123"}


def test_step_output_reference():
    out = resolve(
        {"tables": "${steps.extract.outputs.tables}"},
        parameters={},
        step_outputs={"extract": {"tables": [{"name": "Rev", "rows": [["x"]]}]}},
    )
    assert out == {"tables": [{"name": "Rev", "rows": [["x"]]}]}


def test_typed_passthrough_for_full_string_ref():
    """A bare ${ref} returns the typed value, not str."""
    out = resolve(
        "${steps.extract.outputs.count}",
        parameters={},
        step_outputs={"extract": {"count": 42}},
    )
    assert out == 42 and isinstance(out, int)


def test_interpolated_substring():
    out = resolve(
        "doc-${parameters.id}-final",
        parameters={"id": "abc"},
        step_outputs={},
    )
    assert out == "doc-abc-final"


def test_missing_ref_resolves_to_none_in_object_or_empty_in_string():
    obj = resolve({"x": "${parameters.missing}"}, parameters={}, step_outputs={})
    assert obj == {"x": None}
    s = resolve("prefix-${parameters.missing}-suffix", parameters={}, step_outputs={})
    assert s == "prefix--suffix"


def test_nested_lookup():
    out = resolve(
        "${steps.s.outputs.deep.nested.value}",
        parameters={},
        step_outputs={"s": {"deep": {"nested": {"value": "found"}}}},
    )
    assert out == "found"


def test_list_index_lookup():
    out = resolve(
        "${steps.s.outputs.items.0.name}",
        parameters={},
        step_outputs={"s": {"items": [{"name": "first"}, {"name": "second"}]}},
    )
    assert out == "first"


def test_recursive_resolution_in_lists():
    out = resolve(
        ["${parameters.a}", {"k": "${parameters.b}"}, "static"],
        parameters={"a": 1, "b": 2},
        step_outputs={},
    )
    assert out == [1, {"k": 2}, "static"]
