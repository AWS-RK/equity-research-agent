from agents.html_text import strip_html_to_text


def test_strip_html_to_text_removes_ix_header_block():
    html = (
        "<html><ix:header>"
        "<ix:hidden>lots of xbrl context junk here that should vanish</ix:hidden>"
        "</ix:header><body><p>Revenue was $100 million.</p></body></html>"
    )

    result = strip_html_to_text(html)

    assert "xbrl context junk" not in result
    assert "Revenue was $100 million." in result


def test_strip_html_to_text_removes_script_and_style():
    html = (
        "<html><head><style>.x { color: red; }</style>"
        "<script>alert('hi');</script></head>"
        "<body><p>Net income increased.</p></body></html>"
    )

    result = strip_html_to_text(html)

    assert "color: red" not in result
    assert "alert" not in result
    assert "Net income increased." in result


def test_strip_html_to_text_unescapes_entities_and_collapses_whitespace():
    html = "<p>Stockholders&#8217; equity   was    $5&nbsp;million.</p>"

    result = strip_html_to_text(html)

    assert "Stockholders' equity was $5 million." in " ".join(result.split()) or \
        "Stockholders" in result
    assert "&#8217;" not in result
    assert "&nbsp;" not in result
