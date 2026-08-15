from app.research_document_reader import _read_html


def test_html_reader_extracts_article_and_same_domain_links():
    result = _read_html("https://example.com/news/a", """
      <html><head><title>Case</title></head><body><nav>menu</nav><article>
      <h1>Seizure</h1><p>Container MSKU1234567 was seized.</p>
      <a href='/evidence'>Evidence</a><a href='https://other.example/x'>Other</a>
      </article></body></html>
    """)
    assert result.title == "Case"
    assert "MSKU1234567" in result.text
    assert result.links == ["https://example.com/evidence"]
    assert "menu" not in result.text


def test_html_reader_exposes_images_for_ocr_followup():
    result = _read_html("https://example.com/a", "<article><img src='/container.jpg'><p>case</p></article>")
    assert result.images == ["https://example.com/container.jpg"]
