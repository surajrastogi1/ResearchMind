import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select
from pypdf import PdfReader
import json

from app.database import get_session
from app.models import User, Project, ProjectCreate, ProjectPDF, ProjectChunk
from app.security import get_current_user
from app.utils.text_utils import clean_extracted_text, chunk_text
from app.utils.ai_helpers import generate_text_embedding

router = APIRouter(prefix="/projects", tags=["Projects & Document Core"])
UPLOAD_DIR = "uploads"

@router.post("")
def create_project(project_data: ProjectCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    new_project = Project(name=project_data.name, description=project_data.description, user_id=current_user.id)
    session.add(new_project)
    session.commit()
    session.refresh(new_project)
    return {"message": "Project Created Successfully", "project": new_project}

@router.get("")
def get_projects(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return session.exec(select(Project).where(Project.user_id == current_user.id)).all()

@router.post("/{project_id}/upload")
def upload_pdf(project_id: int, file: UploadFile = File(...), session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    project = session.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    safe_filename = f"proj_{project_id}_{file.filename}"
    file_save_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    with open(file_save_path, "wb") as buffer:
        buffer.write(file.file.read())

    new_pdf_record = ProjectPDF(filename=file.filename, filepath=file_save_path, project_id=project.id)
    session.add(new_pdf_record)
    session.commit()
    session.refresh(new_pdf_record)
    return {"message": f"File `{file.filename}` uploaded successfully!", "db_record_id": new_pdf_record.id}

@router.get("/{project_id}/pdfs/{pdf_id}/read")
def read_pdf(project_id: int, pdf_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    project = session.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    pdf_record = session.get(ProjectPDF, pdf_id)
    if not pdf_record:
        raise HTTPException(status_code=404, detail="PDF Record not found")
    
    # Check if already processed
    existing_chunks = session.exec(select(ProjectChunk).where(ProjectChunk.pdf_id == pdf_id)).all()
    if existing_chunks:
        return {"message": "PDF already processed", "total_chunks_stored": len(existing_chunks)}

    reader = PdfReader(pdf_record.filepath)
    chunk_counter = 0
    stored_chunks = []

    for page_num, page in enumerate(reader.pages):
        raw_text = page.extract_text()
        cleaned_text = clean_extracted_text(raw_text)
        if not cleaned_text:
            continue
        
        page_chunks = chunk_text(cleaned_text, chunk_size=500, chunk_overlap=50)
        for chunk_payload in page_chunks:
            vector_list = generate_text_embedding(chunk_payload)
            db_chunk = ProjectChunk(
                chunk_index=chunk_counter,
                text_content=chunk_payload,
                embedding=json.dumps(vector_list),
                page_no=page_num + 1,
                pdf_id=pdf_record.id
            )
            session.add(db_chunk)
            stored_chunks.append(db_chunk)
            chunk_counter += 1

    session.commit()
    return {"message": "PDF Parsed and Vectorized successfully!", "total_chunks_created": len(stored_chunks)}