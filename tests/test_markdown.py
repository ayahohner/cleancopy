from prose_lint.markdown import segments


def test_code_and_math_become_placeholders():
    [seg] = segments("A `choose` call returns $v$ quickly.\n")
    assert "`" not in seg.text and "$" not in seg.text
    assert seg.restore(seg.text) == "A `choose` call returns $v$ quickly."


def test_front_matter_and_lines():
    src = '---\ntitle: "A title"\ndescription: Some text.\n---\n\nFirst.\n\n- Item.\n'
    assert [(s.text, s.line) for s in segments(src)] == [("A title", 2), ("Some text.", 3), ("First.", 6), ("Item.", 8)]


def test_code_blocks_are_skipped():
    assert segments("```\nit decides\n```\n") == []
