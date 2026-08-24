import pytest

from pyfoldable.application.ui_render import build_markdown_table


def test_markdown_table_escapes_windows_newlines_pipes_and_formats_numbers():
    table = build_markdown_table(
        [
            {"Name": "A|B", "Note": "first\r\nsecond", "Value": 1.23456789},
            {"Name": None, "Note": "single\rline", "Value": 2},
        ]
    )

    assert "A\\|B" in table
    assert "first<br>second" in table
    assert "single<br>line" in table
    assert "1.23457" in table
    assert "None" not in table


def test_markdown_table_returns_empty_text_for_no_rows():
    assert build_markdown_table([]) == ""


def test_markdown_table_rejects_inconsistent_column_schema():
    with pytest.raises(ValueError, match="ordered column schema"):
        build_markdown_table([{"A": 1}, {"B": 2}])
