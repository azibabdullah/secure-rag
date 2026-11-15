from docx import Document
from pypdf import PdfWriter
import pytest
from src.ingestion.loader import load_pages


def test_docx_preserves_table_order_and_heading(tmp_path):
    doc = Document()
    doc.add_heading('Optics', 1)
    doc.add_paragraph('First paragraph')
    doc.add_table(rows=1, cols=1).cell(0, 0).text = 'Middle table'
    doc.add_paragraph('Last paragraph')
    path = tmp_path / 'test.docx'
    doc.save(path)
    pages = load_pages(path)
    text = '\n'.join(row['text'] for row in pages)
    assert text.index('First paragraph') < text.index('Middle table') < text.index('Last paragraph')
    assert pages[-1]['section'] == 'Optics'


def test_scanned_page_cannot_silently_disappear(tmp_path, monkeypatch):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    path = tmp_path / 'scan.pdf'
    with path.open('wb') as handle:
        writer.write(handle)
    with pytest.raises(ValueError, match='Enable local OCR'):
        load_pages(path)
    monkeypatch.setattr('src.ingestion.loader._ocr_page', lambda data, index: 'OCR extracted text')
    pages = load_pages(path, ocr=True)
    assert pages[0]['page'] == 1 and pages[0]['extraction'] == 'ocr'
    assert pages[0]['text'] == 'OCR extracted text'
