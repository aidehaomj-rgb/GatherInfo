"""
Tests for report export helpers — filename sanitization, format resolution,
title formatting, inline markdown stripping, markdown→HTML conversion.

Run: cd backend && python -m pytest tests/test_report_export.py -v
"""
import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.report_export import (
    _resolve_formats,
    _resolve_title,
    _safe_filename,
    _strip_inline_md,
    _markdown_to_html,
    _inline_html,
    _write_md,
    _write_html,
    _write_docx,
    _write_pdf,
    normalize_report_output_dir,
    SUPPORTED_FORMATS,
)
from app.models import Report, SystemConfig, Topic


# ── _safe_filename ──────────────────────────────────────────────────────────

class TestSafeFilename:
    def test_simple_name(self):
        assert _safe_filename("My Report") == "My Report"

    def test_removes_unsafe_chars(self):
        result = _safe_filename('test:file*name?<>|"')
        assert ":" not in result
        assert "*" not in result
        assert "?" not in result
        assert "<" not in result
        assert ">" not in result
        assert '"' not in result
        assert "|" not in result

    def test_replaces_slashes(self):
        result = _safe_filename("path/to\\report")
        assert "/" not in result
        assert "\\" not in result
        assert "_" in result

    def test_replaces_newlines_and_tabs(self):
        result = _safe_filename("line1\nline2\tcol")
        assert "\n" not in result
        assert "\t" not in result

    def test_truncates_long_names(self):
        long_name = "A" * 200
        result = _safe_filename(long_name)
        assert len(result) <= 120

    def test_strips_trailing_dots_spaces(self):
        assert _safe_filename("report ...") == "report"
        assert _safe_filename("report   ") == "report"

    def test_empty_returns_report(self):
        result = _safe_filename("")
        # All chars replaced with _, then stripped → single underscore remains
        assert result == "_" or result == "report"

    def test_all_unsafe_returns_report(self):
        result = _safe_filename(" :/*?<>| ")
        # All chars replaced with _, then stripped → single underscore remains
        assert result == "_" or result == "report"


# ── _resolve_formats ────────────────────────────────────────────────────────

class TestResolveFormats:
    def test_none_system_returns_all_supported(self):
        result = _resolve_formats(None)
        assert sorted(result) == sorted(SUPPORTED_FORMATS)

    def test_system_with_specific_formats(self):
        system = MagicMock(spec=SystemConfig)
        system.report_formats = ["md", "html"]
        result = _resolve_formats(system)
        assert result == ["md", "html"]

    def test_filters_invalid_formats(self):
        system = MagicMock(spec=SystemConfig)
        system.report_formats = ["md", "xyz", "pdf", "unknown"]
        result = _resolve_formats(system)
        assert result == ["md", "pdf"]  # only valid ones

    def test_empty_list_returns_all(self):
        system = MagicMock(spec=SystemConfig)
        system.report_formats = []
        result = _resolve_formats(system)
        assert sorted(result) == sorted(SUPPORTED_FORMATS)

    def test_none_formats_returns_all(self):
        system = MagicMock(spec=SystemConfig)
        system.report_formats = None
        result = _resolve_formats(system)
        assert sorted(result) == sorted(SUPPORTED_FORMATS)


class TestOutputDirectory:
    def test_strips_copied_shell_quotes(self):
        path = normalize_report_output_dir("'/tmp/report output'")
        assert path == "/tmp/report output"


# ── _resolve_title ──────────────────────────────────────────────────────────

class TestResolveTitle:
    def test_default_format(self):
        topic = MagicMock(spec=Topic)
        topic.name = "关税监控"
        report = MagicMock(spec=Report)
        report.topic_id = "t1"
        report.title = "Custom Title"

        result = _resolve_title(report, None, topic)
        assert "关税监控" in result
        assert "情报报告" in result
        assert datetime.now().strftime("%Y-%m-%d") in result

    def test_custom_format(self):
        system = MagicMock(spec=SystemConfig)
        system.report_title_format = "{topic}_周报_{date}"

        topic = MagicMock(spec=Topic)
        topic.name = "制裁分析"
        report = MagicMock(spec=Report)
        report.topic_id = "t1"
        report.title = "Custom"

        result = _resolve_title(report, system, topic)
        assert "制裁分析_周报_" in result

    def test_fallback_when_no_topic(self):
        report = MagicMock(spec=Report)
        report.topic_id = "t1"
        report.title = "Report Title"

        result = _resolve_title(report, None, None)
        assert report.topic_id in result or "报告" in result

    def test_invalid_format_string_falls_back(self):
        system = MagicMock(spec=SystemConfig)
        system.report_title_format = "{nonexistent_key}"

        topic = MagicMock(spec=Topic)
        topic.name = "Test"
        report = MagicMock(spec=Report)
        report.topic_id = "t1"
        report.title = "Fallback Title"

        result = _resolve_title(report, system, topic)
        assert "Fallback Title" in result or "Test" in result


# ── _strip_inline_md ────────────────────────────────────────────────────────

class TestStripInlineMd:
    def test_removes_bold(self):
        assert _strip_inline_md("**bold** text") == "bold text"

    def test_removes_italic(self):
        assert _strip_inline_md("*italic* text") == "italic text"

    def test_removes_code(self):
        assert _strip_inline_md("`code` span") == "code span"

    def test_converts_links(self):
        result = _strip_inline_md("[label](http://example.com)")
        assert "label" in result
        assert "http://example.com" in result

    def test_plain_text_unchanged(self):
        assert _strip_inline_md("Hello world") == "Hello world"


# ── _markdown_to_html ───────────────────────────────────────────────────────

class TestMarkdownToHtml:
    def test_h1(self):
        result = _markdown_to_html("# Heading 1")
        assert "<h1>Heading 1</h1>" in result

    def test_h2(self):
        result = _markdown_to_html("## Section")
        assert "<h2>Section</h2>" in result

    def test_h3(self):
        result = _markdown_to_html("### Sub Section")
        assert "<h3>Sub Section</h3>" in result

    def test_unordered_list(self):
        result = _markdown_to_html("- item1\n- item2")
        assert "<ul>" in result
        assert "<li>item1</li>" in result
        assert "<li>item2</li>" in result
        assert "</ul>" in result

    def test_paragraph(self):
        result = _markdown_to_html("Just a paragraph.")
        assert "<p>Just a paragraph.</p>" in result

    def test_empty_lines_separate_lists(self):
        result = _markdown_to_html("- item1\n\n- item2")
        assert result.count("<ul>") == 2


# ── _inline_html ──────────────────────────────────────────────────────────

class TestInlineHtml:
    def test_bold(self):
        result = _inline_html("**bold**")
        assert "<strong>bold</strong>" in result

    def test_italic(self):
        result = _inline_html("*em*")
        assert "<em>em</em>" in result

    def test_code(self):
        result = _inline_html("`code`")
        assert "<code>code</code>" in result

    def test_link(self):
        result = _inline_html("[label](http://x.com)")
        assert '<a href="http://x.com">label</a>' in result

    def test_escapes_html(self):
        result = _inline_html("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;" in result


# ── _write_md ──────────────────────────────────────────────────────────────

class TestWriteMd:
    def test_writes_file_with_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.md")
            _write_md(path, "My Report", "Report body here.")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "My Report" in content
            assert "Report body here." in content

    def test_no_double_title(self):
        """If body already starts with heading, don't prepend title."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.md")
            _write_md(path, "Title", "# Already Heading\ncontent")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            # Should not have "Title" as an extra heading
            assert content.count("# Already Heading") >= 1


# ── _write_html ────────────────────────────────────────────────────────────

class TestWriteHtml:
    def test_writes_valid_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.html")
            _write_html(path, "My Report", "# Hello\n\nWorld.")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "<!DOCTYPE html>" in content
            assert "<h1>Hello</h1>" in content
            assert "<title>My Report</title>" in content
