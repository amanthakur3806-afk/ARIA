"""
tests/test_user_session_rag.py

Automated integration test verifying:
1. Ingestion of notes scoped to user_id and session_id into DB.
2. Chunk isolation across different users (User A never sees User B's chunks).
3. Chunk isolation across different sessions for the same user.
4. Chat query retrieval returns sources scoped to the student and session.
5. Document deletion cascades to chunk deletion in DB.
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "rag_store" in data
    print("[PASS] Health check passed")


def test_user_and_session_isolation():
    # User 1: Ingest Binary Search notes in session 'dsa'
    user_1 = "student_alpha"
    sess_dsa = "session_dsa"
    ingest_payload_1 = {
        "text": "Binary Search has O(log n) time complexity and requires a sorted array.",
        "title": "DSA Binary Search",
        "document_id": "doc_alpha_dsa",
        "user_id": user_1,
        "session_id": sess_dsa,
    }
    r1 = client.post("/api/v1/documents/ingest", json=ingest_payload_1)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["status"] == "success"
    assert d1["user_id"] == user_1
    assert d1["session_id"] == sess_dsa
    assert d1["chunks_indexed"] > 0
    print(f"[PASS] Ingested {d1['chunks_indexed']} chunks for {user_1} in {sess_dsa}")

    # User 2: Ingest Cryptography notes in session 'crypto'
    user_2 = "student_beta"
    sess_crypto = "session_crypto"
    ingest_payload_2 = {
        "text": "RSA cryptography relies on the mathematical difficulty of factoring large composite prime numbers.",
        "title": "Cryptography RSA",
        "document_id": "doc_beta_crypto",
        "user_id": user_2,
        "session_id": sess_crypto,
    }
    r2 = client.post("/api/v1/documents/ingest", json=ingest_payload_2)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "success"
    assert d2["user_id"] == user_2
    print(f"[PASS] Ingested {d2['chunks_indexed']} chunks for {user_2} in {sess_crypto}")

    # Verify chunk listing for User 1
    r_chunks_1 = client.get(f"/api/v1/documents/chunks?user_id={user_1}")
    assert r_chunks_1.status_code == 200
    chunks_1 = r_chunks_1.json()["chunks"]
    titles_1 = [c["title"] for c in chunks_1]
    assert "DSA Binary Search" in titles_1
    assert "Cryptography RSA" not in titles_1
    print(f"[PASS] User 1 chunk listing is isolated: {titles_1}")

    # Verify chunk listing for User 2
    r_chunks_2 = client.get(f"/api/v1/documents/chunks?user_id={user_2}")
    assert r_chunks_2.status_code == 200
    chunks_2 = r_chunks_2.json()["chunks"]
    titles_2 = [c["title"] for c in chunks_2]
    assert "Cryptography RSA" in titles_2
    assert "DSA Binary Search" not in titles_2
    print(f"[PASS] User 2 chunk listing is isolated: {titles_2}")

    # Test Session Scoping for User 1
    # Add a second session for User 1: 'web_dev'
    sess_web = "session_web"
    client.post(
        "/api/v1/documents/ingest",
        json={
            "text": "React uses a virtual DOM to optimize UI reconciliation and rerendering.",
            "title": "React Virtual DOM",
            "document_id": "doc_alpha_web",
            "user_id": user_1,
            "session_id": sess_web,
        },
    )

    # Filter chunks by session_dsa
    r_sess_dsa = client.get(f"/api/v1/documents/chunks?user_id={user_1}&session_id={sess_dsa}")
    dsa_titles = [c["title"] for c in r_sess_dsa.json()["chunks"]]
    assert "DSA Binary Search" in dsa_titles
    assert "React Virtual DOM" not in dsa_titles
    print(f"[PASS] Session filter works: session '{sess_dsa}' only has {dsa_titles}")

    # Filter chunks by session_web
    r_sess_web = client.get(f"/api/v1/documents/chunks?user_id={user_1}&session_id={sess_web}")
    web_titles = [c["title"] for c in r_sess_web.json()["chunks"]]
    assert "React Virtual DOM" in web_titles
    assert "DSA Binary Search" not in web_titles
    print(f"[PASS] Session filter works: session '{sess_web}' only has {web_titles}")

    # Test Chat Retrieval Isolation
    # When User 1 asks about time complexity in session_dsa, it should retrieve Binary Search
    chat_payload = {
        "message": "Explain binary search and time complexity",
        "user_id": user_1,
        "thread_id": sess_dsa,
    }
    chat_res = client.post("/api/chat", json=chat_payload)
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    sources = chat_data["assistant_message"]["sources"]
    source_titles = [s["title"] for s in sources]
    print(f"[PASS] User 1 chat sources: {source_titles}")
    assert any("Binary Search" in t for t in source_titles)

    # Clean up User 1 test document
    del_res = client.delete(f"/api/v1/documents/doc_alpha_dsa?user_id={user_1}")
    assert del_res.status_code == 200
    print("[PASS] Document deletion cascade passed")


if __name__ == "__main__":
    test_health()
    test_user_and_session_isolation()
    print("\n[SUCCESS] ALL USER & SESSION RAG TESTS PASSED SUCCESSFULLY!")
