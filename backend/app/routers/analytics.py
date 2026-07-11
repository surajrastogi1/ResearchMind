import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import User, Project, ProjectPDF, ProjectChunk, ChatMessage
from app.security import get_current_user
from app.utils.ai_helpers import (
    generate_text_embedding,
    calculate_cosine_similarity,
    generate_llm_answer_with_memory,
    generate_pdf_summary,
    generate_pdf_notes,
    generate_pdf_flashcards,
    generate_pdf_quiz,
    extract_pdf_keywords,
    classify_pdf_topic,
    cluster_project_documents,
    generate_pdf_recommendations
)

router = APIRouter(tags=["Document Analytics & ML"])


def verify_project_and_pdf(project_id: int, pdf_id: int, session: Session, user_id: int) -> ProjectPDF:
    """Reusable structural guard to handle security and data existence checks."""
    project = session.get(Project, project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    
    pdf_record = session.get(ProjectPDF, pdf_id)
    if not pdf_record or pdf_record.project_id != project_id:
        raise HTTPException(status_code=404, detail="PDF record not found in this project")
    
    return pdf_record


@router.post("/test-embedding")
def test_embedding(text: str):
    vector = generate_text_embedding(text)
    if not vector:
        raise HTTPException(status_code=500, detail="Failed to connect to Gemini API Key")
    
    return {
        "text_provided": text,
        "vector_dimensions": len(vector),
        "sample_vector_values": vector[:5]
    }


@router.post("/projects/{project_id}/pdfs/{pdf_id}/search")
def semantic_search_pdf(
    project_id: int,
    pdf_id: int,
    query: str,
    limit: int = 3,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    project = session.get(Project, project_id)
    if not project or (project.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not Authorized to access this project")
    
    query_vector = generate_text_embedding(query)
    if not query_vector:
        raise HTTPException(status_code=500, detail="Failed to generate embedding for the search query")
    
    chunks = session.exec(select(ProjectChunk).where(ProjectChunk.pdf_id == pdf_id)).all()
    if not chunks:
        raise HTTPException(status_code=404, detail="No processed chunks found for this PDF.")
    
    search_results = []
    for chunk in chunks:
        if not chunk.embedding:
            continue

        chunk_vector = json.loads(chunk.embedding)
        similarity_score = calculate_cosine_similarity(query_vector, chunk_vector)

        search_results.append({
            "chunk_id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text_content,
            "similarity_score": similarity_score
        })

    search_results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return {
        "query": query,
        "results": search_results[:limit]
    }


@router.post("/projects/{project_id}/pdfs/{pdf_id}/chat")
def chat_with_pdf(
    project_id: int,
    pdf_id: int,
    question: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    
    pdf_record = verify_project_and_pdf(project_id, pdf_id, session, current_user.id)

    query_vector = generate_text_embedding(question)
    if not query_vector:
        raise HTTPException(status_code=500, detail="Failed to vectorize question")
    
    chunks = session.exec(select(ProjectChunk).where(ProjectChunk.pdf_id == pdf_id)).all()
    if not chunks:
        raise HTTPException(status_code=404, detail="No chunks found. Process the PDF first.")
    
    ranked_chunks = []
    for chunk in chunks:
        if not chunk.embedding:
            continue
        chunk_vector = json.loads(chunk.embedding)
        score = calculate_cosine_similarity(query_vector, chunk_vector)
        ranked_chunks.append((score, chunk.text_content, chunk.page_no))

    ranked_chunks.sort(key=lambda x: x[0], reverse=True)
    top_context = ranked_chunks[:3]
    top_context_texts = [item[1] for item in top_context]

    past_messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.pdf_id == pdf_id)
        .order_by(ChatMessage.timestamp.desc())
        .limit(6)
    ).all()
    past_messages.reverse()

    history_context = ""
    for msg in past_messages:
        history_context += f"{msg.sender.upper()}: {msg.message_text}\n"

    # Contextually include the source file trace string
    llm_output = generate_llm_answer_with_memory(
        question=f"Regarding the file '{pdf_record.filename}': {question}", 
        context_chunks=top_context_texts, 
        history_context=history_context
    )
    ai_answer = llm_output.get("answer", "")
    suggested_followups = llm_output.get("suggested_followups", [])

    user_record = ChatMessage(sender="user", message_text=question, pdf_id=pdf_id)
    ai_record = ChatMessage(sender="ai", message_text=ai_answer, pdf_id=pdf_id)

    session.add(user_record)
    session.add(ai_record)
    session.commit()

    return {
        "question": question,
        "answer": ai_answer,
        "sources_used": len(top_context_texts),
        "suggested_followups": suggested_followups,
        "citations": [
            {
                "index": i, 
                "page": item[2], 
                "text_snippet": item[1][:150] + "..."
            } 
            for i, item in enumerate(top_context)
        ]
    }


@router.get("/projects/{project_id}/pdfs/{pdf_id}/history")
def get_chat_history(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    pdf_record = verify_project_and_pdf(project_id, pdf_id, session, current_user.id)

    messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.pdf_id == pdf_id)
        .order_by(ChatMessage.timestamp.asc())
    ).all()

    return {
        "pdf_id": pdf_id,
        "filename": pdf_record.filename,
        "total_messages": len(messages),
        "history": [
            {
                "message_id": msg.id,
                "sender": msg.sender,
                "message_text": msg.message_text,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in messages
        ]
    }


@router.post("/projects/{project_id}/pdfs/{pdf_id}/summary")
def get_pdf_summary_endpoint(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    pdf_record = verify_project_and_pdf(project_id, pdf_id, session, current_user.id)
    
    chunks = session.exec(
        select(ProjectChunk)
        .where(ProjectChunk.pdf_id == pdf_id)
        .order_by(ProjectChunk.id.asc())
    ).all()

    if not chunks:
        raise HTTPException(status_code=400, detail="No processed text content found for this PDF.")
    
    chunk_texts = [c.text_content for c in chunks]
    summary_markdown = generate_pdf_summary(pdf_record.filename, chunk_texts)

    return {
        "pdf_id": pdf_id,
        "filename": pdf_record.filename,
        "summary": summary_markdown
    }


@router.post("/projects/{project_id}/pdfs/{pdf_id}/notes")
def get_pdf_notes_endpoint(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    pdf_record = verify_project_and_pdf(project_id, pdf_id, session, current_user.id)

    chunks = session.exec(
        select(ProjectChunk)
        .where(ProjectChunk.pdf_id == pdf_id)
        .order_by(ProjectChunk.id.asc())
    ).all()

    if not chunks:
        raise HTTPException(status_code=400, detail="No processed text content found. Run /read first.")

    chunk_texts = [c.text_content for c in chunks]
    notes_markdown = generate_pdf_notes(pdf_record.filename, chunk_texts)

    return {
        "pdf_id": pdf_id,
        "filename": pdf_record.filename,
        "study_notes": notes_markdown
    }


@router.post("/projects/{project_id}/pdfs/{pdf_id}/flashcards")
def get_pdf_flashcards_endpoint(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    pdf_record = verify_project_and_pdf(project_id, pdf_id, session, current_user.id)

    chunks = session.exec(
        select(ProjectChunk)
        .where(ProjectChunk.pdf_id == pdf_id)
        .order_by(ProjectChunk.id.asc())
    ).all()

    if not chunks:
        raise HTTPException(status_code=400, detail="No processed text content found. Run /read first.")

    chunk_texts = [c.text_content for c in chunks]
    flashcards_list = generate_pdf_flashcards(pdf_record.filename, chunk_texts)

    return {
        "pdf_id": pdf_id,
        "filename": pdf_record.filename,
        "count": len(flashcards_list),
        "flashcards": flashcards_list
    }


@router.post("/projects/{project_id}/pdfs/{pdf_id}/quiz")
def get_pdf_quiz_endpoint(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    pdf_record = verify_project_and_pdf(project_id, pdf_id, session, current_user.id)
    
    chunks = session.exec(
        select(ProjectChunk)
        .where(ProjectChunk.pdf_id == pdf_id)
        .order_by(ProjectChunk.id.asc())
    ).all()

    if not chunks:
        raise HTTPException(status_code=400, detail="No text content found. Run /read first.")

    chunk_texts = [c.text_content for c in chunks]
    quiz_questions = generate_pdf_quiz(pdf_record.filename, chunk_texts)

    return {
        "pdf_id": pdf_id,
        "filename": pdf_record.filename,
        "total_questions": len(quiz_questions),
        "quiz": quiz_questions
    }


@router.get("/projects/{project_id}/pdfs/{pdf_id}/stats")
def get_pdf_statistics(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    pdf_record = verify_project_and_pdf(project_id, pdf_id, session, current_user.id)

    chunks = session.exec(
        select(ProjectChunk)
        .where(ProjectChunk.pdf_id == pdf_id)
    ).all()

    if not chunks:
        raise HTTPException(status_code=400, detail="No text content found. Please run /read first.")

    total_chunks = len(chunks)
    total_characters = 0
    total_words = 0
    total_paragraphs = 0

    for chunk in chunks:
        text = chunk.text_content
        total_characters += len(text)
        total_words += len(text.split())
        
        paragraphs = [p for p in text.split("\n") if p.strip()]
        total_paragraphs += len(paragraphs)

    return {
        "pdf_id": pdf_id,
        "filename": pdf_record.filename,
        "metrics": {
            "total_chunks": total_chunks,
            "total_characters": total_characters,
            "total_words": total_words,
            "estimated_paragraphs": total_paragraphs
        }
    }


@router.post("/projects/{project_id}/pdfs/{pdf_id}/keywords")
def get_pdf_keywords_endpoint(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    pdf_record = verify_project_and_pdf(project_id, pdf_id, session, current_user.id)

    chunks = session.exec(
        select(ProjectChunk)
        .where(ProjectChunk.pdf_id == pdf_id)
        .order_by(ProjectChunk.id.asc())
    ).all()

    if not chunks:
        raise HTTPException(status_code=400, detail="No processed text content found. Run /read first.")

    chunk_texts = [c.text_content for c in chunks]
    keywords_data = extract_pdf_keywords(pdf_record.filename, chunk_texts)

    return {
        "pdf_id": pdf_id,
        "filename": pdf_record.filename,
        "total_extracted": len(keywords_data),
        "keywords": keywords_data
    }


@router.get("/projects/{project_id}/pdfs/{pdf_id}/reading-time")
def get_pdf_reading_time(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    pdf_record = verify_project_and_pdf(project_id, pdf_id, session, current_user.id)

    chunks = session.exec(
        select(ProjectChunk)
        .where(ProjectChunk.pdf_id == pdf_id)
    ).all()

    if not chunks:
        raise HTTPException(status_code=400, detail="No text data found. Please run /read first.")

    total_words = sum(len(chunk.text_content.split()) for chunk in chunks)
    minutes_average = round(total_words / 200, 1)
    minutes_fast = round(total_words / 300, 1)

    return {
        "pdf_id": pdf_id,
        "filename": pdf_record.filename,
        "word_count_pool": total_words,
        "estimated_reading_time": {
            "average_reader": f"{minutes_average} minutes",
            "fast_reader": f"{minutes_fast} minutes",
            "wpm_benchmarks": {
                "standard_pace": "200 wpm",
                "accelerated_pace": "300 wpm"
            }
        }
    }


@router.post("/projects/{project_id}/pdfs/{pdf_id}/classify")
def get_pdf_topic_classification_endpoint(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    pdf_record = verify_project_and_pdf(project_id, pdf_id, session, current_user.id)
    
    chunks = session.exec(
        select(ProjectChunk)
        .where(ProjectChunk.pdf_id == pdf_id)
        .order_by(ProjectChunk.id.asc())
    ).all()

    if not chunks:
        raise HTTPException(status_code=400, detail="No text content found. Run /read first.")

    chunk_texts = [c.text_content for c in chunks]
    classification_results = classify_pdf_topic(pdf_record.filename, chunk_texts)

    return {
        "pdf_id": pdf_id,
        "filename": pdf_record.filename,
        "classification": classification_results
    }


@router.post("/projects/{project_id}/cluster")
def get_project_document_clusters(
    project_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    project = session.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")

    pdfs = session.exec(
        select(ProjectPDF).where(ProjectPDF.project_id == project_id)
    ).all()

    if len(pdfs) < 1:
        raise HTTPException(status_code=400, detail="Need at least 1 document in the project to run clustering.")

    pdf_list = [{"pdf_id": pdf.id, "filename": pdf.filename} for pdf in pdfs]
    clustering_results = cluster_project_documents(pdf_list)

    return {
        "project_id": project_id,
        "total_documents_analyzed": len(pdfs),
        "results": clustering_results
    }


@router.post("/projects/{project_id}/pdfs/{pdf_id}/recommendations")
def get_pdf_recommendations_endpoint(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    project = session.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")

    target_pdf_record = session.get(ProjectPDF, pdf_id)
    if not target_pdf_record or target_pdf_record.project_id != project_id:
        raise HTTPException(status_code=404, detail="Target PDF record not found in this project")

    all_pdfs = session.exec(
        select(ProjectPDF).where(ProjectPDF.project_id == project_id)
    ).all()

    other_pdfs_list = []
    target_pdf_data = {"pdf_id": target_pdf_record.id, "filename": target_pdf_record.filename}

    for pdf in all_pdfs:
        if pdf.id != pdf_id:
            other_pdfs_list.append({
                "pdf_id": pdf.id,
                "filename": pdf.filename
            })

    if not other_pdfs_list:
        return {
            "target_pdf_id": pdf_id,
            "recommendations": [],
            "message": "No other documents exist in this project to recommend against."
        }

    recommendations = generate_pdf_recommendations(target_pdf_data, other_pdfs_list)
    return {
        "target_pdf_id": pdf_id,
        "filename": target_pdf_record.filename,
        "recommendations": recommendations
    }