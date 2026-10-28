"""
tests/test_document_upload.py

Comprehensive tests for Document Upload, PDF Text Extraction,
Null-Byte Sanitization, and File Handling Guardrails.
"""
import io
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.rag_store import rag_store
from app.main import (
    DocumentIngestRequest,
    delete_document,
    ingest_document,
    list_indexed_chunks,
    upload_document_file,
)

SAMPLE_VALID_PDF_BYTES = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 55 >> stream
BT /F1 24 Tf 100 700 Td (Operating Systems Virtual Memory) Tj ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000246 00000 n 
0000000353 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
424
%%EOF"""


def test_upload_text_file():
    """Verify plain text and Markdown files upload and index chunks correctly."""
    user_id = "test_student_txt"
    session_id = "session_notes"
    content = b"Distributed systems rely on consensus algorithms like Raft and Paxos."
    file_obj = UploadFile(filename="consensus.md", file=io.BytesIO(content))

    res = upload_document_file(
        file=file_obj,
        user_id=user_id,
        session_id=session_id,
        title="Consensus Notes",
    )

    assert res["status"] == "success"
    assert res["user_id"] == user_id
    assert res["session_id"] == session_id
    assert res["title"] == "Consensus Notes"
    assert res["chunks_indexed"] >= 1
    assert rag_store.total_chunks(user_id=user_id, session_id=session_id) >= 1

    # Clean up
    delete_document(document_id=res["document_id"], user_id=user_id)


def test_upload_pdf_file():
    """Verify PDF files are parsed with pypdf and chunks are indexed."""
    user_id = "test_student_pdf"
    session_id = "session_os"
    file_obj = UploadFile(filename="lecture_vm.pdf", file=io.BytesIO(SAMPLE_VALID_PDF_BYTES))

    res = upload_document_file(
        file=file_obj,
        user_id=user_id,
        session_id=session_id,
    )

    assert res["status"] == "success"
    assert res["user_id"] == user_id
    assert res["title"] == "lecture_vm"
    assert res["chunks_indexed"] >= 1

    chunks = list_indexed_chunks(user_id=user_id, session_id=session_id)["chunks"]
    assert len(chunks) >= 1
    assert any("Virtual Memory" in c["text"] for c in chunks)

    # Clean up
    delete_document(document_id=res["document_id"], user_id=user_id)


def test_upload_empty_or_scanned_pdf():
    """Verify empty or scanned PDFs without selectable text raise clean 400 error."""
    import pypdf

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)

    file_obj = UploadFile(filename="blank.pdf", file=buf)
    with pytest.raises(HTTPException) as exc_info:
        upload_document_file(file=file_obj, user_id="student_fail")

    assert exc_info.value.status_code == 400
    assert "No selectable text found" in exc_info.value.detail


def test_upload_file_oversized():
    """Verify files larger than 10MB are rejected with 400 limit error."""
    huge_payload = b"A" * (10 * 1024 * 1024 + 1024)
    file_obj = UploadFile(filename="huge.txt", file=io.BytesIO(huge_payload))

    with pytest.raises(HTTPException) as exc_info:
        upload_document_file(file=file_obj, user_id="student_huge")

    assert exc_info.value.status_code == 400
    assert "10MB" in exc_info.value.detail


def test_ingest_null_byte_sanitization():
    """Verify text with embedded null bytes is sanitized and does not crash SQLite."""
    user_id = "test_student_null"
    session_id = "thread-1"
    dirty_text = "Page Table\x00Entry consists of\x00 frame number and flags."

    req = DocumentIngestRequest(
        text=dirty_text,
        title="Memory\x00 Management",
        user_id=user_id,
        session_id=session_id,
    )
    res = ingest_document(payload=req)

    assert res["status"] == "success"
    assert "\x00" not in res["title"]
    assert res["chunks_indexed"] >= 1

    # Verify stored chunk does not have null byte
    chunks = list_indexed_chunks(user_id=user_id, session_id=session_id)["chunks"]
    assert len(chunks) >= 1
    for chk in chunks:
        assert "\x00" not in chk["text"]

    # Clean up
    delete_document(document_id=res["document_id"], user_id=user_id)


def test_ingest_empty_text():
    """Verify empty or whitespace-only text is rejected with 400."""
    req = DocumentIngestRequest(
        text="   \x00   ",
        user_id="test_student_empty",
    )
    with pytest.raises(HTTPException) as exc_info:
        ingest_document(payload=req)

    assert exc_info.value.status_code == 400
    assert "cannot be empty" in exc_info.value.detail
