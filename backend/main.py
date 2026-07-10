from fastapi import FastAPI,HTTPException,Depends,File,UploadFile
from sqlmodel import SQLModel,create_engine,Field,Session,select
from pydantic import EmailStr
from datetime import datetime,timedelta,timezone
from fastapi.security import OAuth2PasswordBearer,OAuth2PasswordRequestForm
from pypdf import PdfReader
from google import genai
from dotenv import load_dotenv
import bcrypt
import jwt
import os
import re
import json
import math

load_dotenv()

upload_dir = "uploads"
os.makedirs(upload_dir,exist_ok=True)


SECRET_KEY = "my_super_secret_key_for_researchmind_ai"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def create_access_tokens(data : dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp" : expire})

    encoded_jwt = jwt.encode(to_encode,SECRET_KEY,algorithm=ALGORITHM)
    return encoded_jwt


def get_password_hash(password: str) -> str:
    # Convert plain text to bytes, salt it, and hash it
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8') # Convert back to a clean text string for the DB

def verify_password(plain_password : str , hashed_password : str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )

def clean_extracted_text(raw_text : str) -> str:
    if not raw_text:
        return ""
    
    text = re.sub(r'\s+',' ',raw_text)

    text = text.strip()

    return text

def chunk_text(text : str,chunk_size : int = 500,chunk_overlap:int = 50) -> list[str]:
    if not text:
        return []
    
    chunks = []
    start = 0
    text_length = len(text)

    while start<text_length:
        end = start+chunk_size
        chunk = text[start:end]
        chunks.append(chunk)

        start += (chunk_size-chunk_overlap)

    return chunks

def generate_text_embedding(text: str) -> list[float]:
    if not text:
        return []
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is missing from .env")
        
    # Initialize the client
    client = genai.Client(api_key=api_key)
    
    try:
        # Make sure this says client.models (PLURAL)
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text
        )
        return response.embeddings[0].values
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google API Error: {str(e)}")

def calculate_cosine_similarity(v1:list[float],v2:list[float]) -> float:
    """Calculate cosine similarity score b/w two numeric vectors"""

    if not v1 or not v2 or (len(v1) != len(v2)):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude_v1 = math.sqrt(sum(a * a for a in v1))
    magnitude_v2 = math.sqrt(sum(b * b for b in v2))

    if magnitude_v1 == 0 or magnitude_v2 == 0:
            return 0.0
    
    return dot_product / (magnitude_v1*magnitude_v2)

def generate_llm_answer_with_memory(question : str, context_chunks: list[str],history_context: str) -> dict:
    """Sends the question and retrieved document context to gemini to generate an answer"""

    api_key = os.getenv("GEMINI_API_Key")
    if not api_key:
        raise HTTPException(status_code=500,detail="API Key is missing")
    client = genai.Client(api_key=api_key)

    joined_context = "\n---\n".join(context_chunks)

    system_prompt = (
        "You are a helpful AI Research Assistant. Use ONLY the provided background context "
        "extracted from the document and the ongoing conversation history to answer the user's question accurately.\n\n"
        "CRITICAL: You must return your response in raw JSON format matching this schema:\n"
        "{\n"
        "  \"answer\": \"Your detailed answer string here...\",\n"
        "  \"suggested_followups\": [\n"
        "    \"Follow-up question 1?\",\n"
        "    \"Follow-up question 2?\",\n"
        "    \"Follow-up question 3?\"\n"
        "  ]\n"
        "}\n"
        "If the answer cannot be found within the provided context, state that the information is not available "
        "in the 'answer' key, and leave 'suggested_followups' as an empty list."
    )
    

    user_prompt = (
        f"Background Context from Document:\n{joined_context}\n\n"
        f"Recent Conversation History:\n{history_context}\n"
        f"USER: {question}\n"
        f"AI:"
    )   

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents= user_prompt,
            config={"system_instruction" : system_prompt,"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Generation Error: {str(e)}")

def generate_pdf_summary(filename : str,context_chunks : list[str]) ->  str:
    """Combines core document chunks and sends them to Gemini to generate a structured summary."""
    client = genai.Client(api_key=os.getenv("GEMINI_API_Key"))

    full_text = "\n".join(context_chunks[:25])

    system_prompt = (
        "You are an expert Research Analyst. Your job is to read the provided text from a document "
        "and generate a highly accurate, professional, comprehensive executive summary.\n\n"
        "Format your response using clean Markdown with the following distinct sections:\n"
        "## 📑 Executive Summary\n"
        "## 🔑 Key Takeaways (Bullet points)\n"
        "## 🎯 Target Audience / Core Subject\n\n"
        "Do not hallucinate. Base your summary strictly on the text provided."
    )
    user_prompt = f"Document Filename: {filename}\n\nDocument Text Content:\n{full_text}"

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config={"system_instruction": system_prompt}
        )
        return response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary Generation Error: {str(e)}")

def generate_pdf_notes(filename: str, context_chunks: list[str]) -> str:
    """Analyzes document chunks to build comprehensive study notes in Markdown format."""
    client = genai.Client(api_key=os.getenv("GEMINI_API_Key"))
    full_text = "\n".join(context_chunks[:25])
    
    system_prompt = (
        "You are an elite academic tutor. Read the provided document text and create "
        "comprehensive, deeply structured study notes.\n\n"
        "Format your output in clean Markdown using these guidelines:\n"
        "- Use clear headings (`##`, `###`) for major topics\n"
        "- **Bold** crucial terminology and core concepts upon first mention\n"
        "- Use bulleted lists to break down complex processes or mechanics\n"
        "- Include a '💡 Deep Dive' blockquote for the most critical insight\n\n"
        "Ensure your notes are highly instructional and stick strictly to the facts provided."
    )

    user_prompt = f"Document Filename: {filename}\n\nSource Content:\n{full_text}"
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config={"system_instruction": system_prompt}
        )
        return response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notes Generation Error: {str(e)}")

def generate_pdf_flashcards(filename: str, context_chunks: list[str]) -> list[dict]:
    """Analyzes text chunks and returns an array of structured Q&A flashcards."""
    client = genai.Client(api_key=os.getenv("GEMINI_API_Key"))
    
    full_text = "\n".join(context_chunks[:25])
    
    system_prompt = (
        "You are an expert educator. Extract key definitions, concepts, and facts "
        "from the provided text and convert them into an array of clear, high-quality study flashcards.\n\n"
        "CRITICAL: You must return your response in raw JSON format matching this schema:\n"
        "[\n"
        "  {\n"
        "    \"front\": \"The question or concept name to display on the front...\",\n"
        "    \"back\": \"The concise definition or answer to display on the back.\"\n"
        "  }\n"
        "]\n"
        "Generate between 5 to 8 flashcards based strictly on the source material."
    )
    
    user_prompt = f"Document Filename: {filename}\n\nSource Content:\n{full_text}"
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config={
                "system_instruction": system_prompt,
                "response_mime_type": "application/json"
            }
        )
        return json.loads(response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flashcard Generation Error: {str(e)}")

def generate_pdf_quiz(filename: str, context_chunks: list[str]) -> list[dict]:
    """Analyzes text chunks and yields an array of structured multiple-choice quiz questions."""
    client = genai.Client(api_key=os.getenv("GEMINI_API_Key"))
    
    full_text = "\n".join(context_chunks[:25])
    
    system_prompt = (
        "You are an expert examiner. Read the provided document content and construct a high-quality "
        "multiple-choice assessment quiz based strictly on the material.\n\n"
        "CRITICAL: You must return your response in raw JSON format matching this schema layout:\n"
        "[\n"
        "  {\n"
        "    \"question\": \"The explicit question string here...\",\n"
        "    \"options\": [\"Option A\", \"Option B\", \"Option C\", \"Option D\"],\n"
        "    \"correct_option_index\": 0\n"
        "  }\n"
        "]\n"
        "Note: 'correct_option_index' must be a 0-indexed integer (0 for Option A, 1 for Option B, etc.). "
        "Generate exactly 5 distinct conceptual questions."
    )
    
    user_prompt = f"Document Filename: {filename}\n\nSource Content:\n{full_text}"
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config={
                "system_instruction": system_prompt,
                "response_mime_type": "application/json"
            }
        )
        return json.loads(response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz Generation Error: {str(e)}")

class User(SQLModel,table=True):

    __tablename__ = "users"

    id: int | None = Field(default=None,primary_key=True)
    username: str = Field(unique=True,index=True)
    email : str = Field(unique=True)
    hashed_password : str 

class UserCreate(SQLModel): #this helps to user enter these things
    username: str
    email: EmailStr
    password: str

class Project(SQLModel, table= True):
    __tablename__ = "projects"

    id : int | None = Field(default=None,primary_key=True)
    name: str = Field(default=None)
    description: str | None= Field(default=None)
    user_id : int= Field(foreign_key="users.id")

class ProjectCreate(SQLModel):
    name:str
    description:str | None = None

class ProjectPDF(SQLModel, table=True):
    __tablename__ = "project_pdfs"

    id : int = Field(default=None,primary_key=True)
    filename : str = Field(default=None)
    filepath :str = Field(default=None)
    uploaded_at : datetime = Field(default_factory=lambda : datetime.now(timezone.utc))

    project_id : int = Field(foreign_key="projects.id")

class ProjectChunk(SQLModel,table=True):
    __tablename__ = "project_chunk"
    id : int = Field(default=None,primary_key=True)
    chunk_index : int = Field(index=True)
    text_content : str
    embedding : str | None = Field(default=None)
    page_no : int | None = Field(default=None)

    pdf_id : int = Field(foreign_key="project_pdfs.id")

class ChatMessage(SQLModel,table=True):
    __tablename__ = "chat_history"
    
    id:int = Field(default=None , primary_key=True)
    sender : str = Field(index=True)
    message_text : str
    timestamp : datetime = Field(default_factory=datetime.utcnow)

    pdf_id : int = Field(foreign_key="project_pdfs.id")



sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

#this talks to database
engine = create_engine(sqlite_url,connect_args={"check_same_thread" : False})


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():  #to open and close DB
    with Session(engine) as session:
        yield session

def get_current_user(token : str = Depends(oauth2_scheme),session : Session = Depends(get_session)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate Credentials",
        headers={"WWW-Authenticate" : "Bearer"}
    )
    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        username : str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise credentials_exception
    return user

app = FastAPI(title="ResearchMind")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def root():
    return {"message" : "API Running and Database Connected"}

@app.post("/register")
def register(user_data : UserCreate, session : Session = Depends(get_session)):
    #1. check if username already exists
    existing_user = session.exec(select(User).where(User.username == user_data.username)).first()
    if existing_user:
        raise HTTPException(status_code=400,detail="Username already exists")
    #2. check if email already exists
    existing_email = session.exec(select(User).where(User.email == user_data.email)).first()
    if existing_email:
        raise HTTPException(status_code=400,detail="Email already exists")
    
    secured_hash_password = get_password_hash(user_data.password)

    new_user = User(
        username=user_data.username,
        email = user_data.email,
        hashed_password = secured_hash_password
    )

    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return {"message" : "User Registered Successfully!" , "user_id" : new_user.id}

@app.post("/login")
def login(login_data : OAuth2PasswordRequestForm = Depends(), session : Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == login_data.username)).first()

    if not user:
        raise HTTPException(
            status_code= 401,
            detail= "Invalid username or password"
        )
    if not verify_password(login_data.password,user.hashed_password):
        raise HTTPException(
            status_code= 401,
            detail= "Invalid username or password"
        )
    
    access_token = create_access_tokens(data = {"sub" : user.username})
    
    return {
        "access_token" : access_token,
        "token_type" : "bearer",
        "username" : user.username
    }

@app.get("/me")
def read_user_me(current_user: User = Depends(get_current_user)):
    return {
        "id" : current_user.id,
        "username" : current_user.username,
        "email" : current_user.email,
        "message" : "Welcome to your protected profile"
    }

@app.post("/projects")
def create_project(
    project_data : ProjectCreate,
    session : Session = Depends(get_session),
    current_user : User = Depends(get_current_user)
):
    new_project = Project(
        name = project_data.name,
        description= project_data.description,
        user_id= current_user.id
    )

    session.add(new_project)
    session.commit()
    session.refresh(new_project)

    return {
        "message" : "Project Created Successfully",
        "project" : new_project
    }

@app.get("/projects")
def get_projects(session : Session = Depends(get_session), current_user : User = Depends(get_current_user)):
    statement = select(Project).where(Project.user_id == current_user.id)
    user_projects = session.exec(statement).all()

    return user_projects

@app.put("/update/{project_id}")
def update_project(
    project_id : int,
    updated_data : ProjectCreate,
    session : Session = Depends(get_session),
    current_user : User = Depends(get_current_user)
):
    project = session.get(Project,project_id)

    if not project:
        raise HTTPException(status_code=404,detail="Project not found")
    
    if (project.user_id != current_user.id):
        raise HTTPException(status_code=403,detail="Not authorized to update this project")
    
    project.name = updated_data.name
    project.description = updated_data.description

    session.add(project)
    session.commit()
    session.refresh(project)

    return {
        "message" : "Project updated successfully",
        "project" : project
    }

@app.delete("/projects/{project_id}")
def delete_project(
    project_id : int,
    session : Session = Depends(get_session),
    current_user : User = Depends(get_current_user)
):
    
    project = session.get(Project,project_id)

    if not project:
        raise HTTPException(status_code=404,detail="Project not found")
    
    if (project.user_id != current_user.id):
        raise HTTPException(status_code=403,detail="Not Authorized to delete this project")
    
    session.delete(project)

    session.commit()

    return {
        "message" : f"Project {project.name} has been successfully deleted"
    }

@app.post("/projects/{project_id}/upload")
def upload_pdf(
    project_id : int,
    file : UploadFile = File(...),
    session : Session = Depends(get_session),
    current_user : User = Depends(get_current_user)
):
    project = session.get(Project,project_id)

    if not project:
        raise HTTPException(status_code=404,detail="Project not Found")
    
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403,detail="Not authorized to access this project")
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400,detail="Only pdf files are allowed")
    
    safe_filename = f"proj_{project_id}_{file.filename}"
    file_save_path = os.path.join(upload_dir,safe_filename)

    try:
        with open(file_save_path,"wb") as buffer:
            contents = file.file.read()
            buffer.write(contents)

    except Exception as e:
        raise HTTPException(status_code=500,detail=f"Failed to save file: {str(e)}")
    
    finally:
        file.file.close()

    new_pdf_record = ProjectPDF(
        filename=file.filename,
        filepath=file_save_path,
        project_id=project.id
    )

    session.add(new_pdf_record)
    session.commit()
    session.refresh(new_pdf_record)

    return {
        "message" : f"File `{file.filename}` uploaded successfully!",
        "db_record_id": new_pdf_record.id,
        "saved_path" : file_save_path,
        "content_type" : file.content_type
    }

@app.get("/projects/{project_id}/pdfs/{pdf_id}/read")
def read_pdf(
    project_id : int,
    pdf_id : int,
    session : Session = Depends(get_session),
    current_user : User = Depends(get_current_user)
):
    
    project = session.get(Project,project_id)

    if not project:
        raise HTTPException(status_code=404,detail="Project Not found")
    
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403,detail="Not authorized to access the pdf")

    pdf_record = session.get(ProjectPDF,pdf_id)

    if not pdf_record:
        raise HTTPException(status_code=404,detail="PDF Record not found")
    
    existing_chunks = session.exec(select(ProjectChunk).where(ProjectChunk.pdf_id == pdf_id)).all()
    if existing_chunks:
        return {
            "message" : "PDF already processed",
            "pdf_id": pdf_record.id,
            "filename": pdf_record.filename,
            "total_chunks_stored": len(existing_chunks),
            "chunks": [ {"index": c.chunk_index, "text": c.text_content[:100] + "..."} for c in existing_chunks ]
        }
    
    if not os.path.exists(pdf_record.filepath):
        raise HTTPException(status_code=404,detail="Physical pdf file missin in storage folder")
    

    
    try:
        reader = PdfReader(pdf_record.filepath)
        stored_chunks_response = []
        chunk_counter = 0

        for page_num,page in enumerate(reader.pages):
            raw_page_text = page.extract_text()
            if not raw_page_text:
                continue

            cleaned_page_text = clean_extracted_text(raw_page_text)
            if not cleaned_page_text:
                continue

            page_chunks = chunk_text(cleaned_page_text,chunk_size=500,chunk_overlap=50)
            
            for chunk_payload in page_chunks:
                vector_list = generate_text_embedding(chunk_payload)

                db_chunk = ProjectChunk(
                        chunk_index=chunk_counter,
                        text_content=chunk_payload,
                        embedding=json.dumps(vector_list),
                        page_no= page_num + 1,  # Saves Page 1, Page 2, etc.
                        pdf_id=pdf_record.id
                    )
                
                session.add(db_chunk)
                stored_chunks_response.append(db_chunk)
                chunk_counter+=1

        if not stored_chunks_response:
            raise HTTPException(status_code=400, detail="The PDF contains no readable text extract.")
        
        session.commit()

    except HTTPException:
        raise HTTPException(status_code=400, detail="The PDF contains no readable text extract.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse the pdf document: {str(e)}")
    
    return {
        "message": "PDF Parsed, split, chunked and database records generated successfully!",
        "pdf_id": pdf_record.id,
        "filename": pdf_record.filename,
        "total_pages": len(reader.pages),
        "total_chunks_created": len(stored_chunks_response),
        "chunks": [ {"index": c.chunk_index, "page": c.page_no, "text": c.text_content[:100] + "..."} for c in stored_chunks_response ]
    }

@app.get("/projects/{project_id}/pdfs/{pdf_id}/chunks")
def get_chunks(
    project_id : int,
    pdf_id : int,
    session : Session = Depends(get_session),
    current_user : User = Depends(get_current_user)
):
    project = session.get(Project,project_id)

    if not project_id or (project.user_id != current_user.id):
        raise HTTPException(status_code=403,detail="Not Authorized")
    
    chunks = session.exec(select(ProjectChunk).where(ProjectChunk.pdf_id == pdf_id)).all()
    return chunks

@app.post("/test-embedding")
def test_embedding(text:str):
    vector = generate_text_embedding(text)
    if not vector:
        raise HTTPException(status_code=500,detail="Failed to connect to Gemini API Key ")
    
    return {
        "text_provided" : text,
        "vector_dimensions" : len(vector),
        "sample_vector_values" : vector[:5]
    }

@app.post("/projects/{project_id}/pdfs/{pdf_id}/search")
def semantic_search_pdf(
    project_id : int,
    pdf_id : int,
    query : str,
    limit : int = 3,
    session : Session = Depends(get_session),
    current_user : User = Depends(get_current_user)
):
    
    project = session.get(Project,project_id)

    if not project or (project.user_id != current_user.id):
        raise HTTPException(status_code=403,detail="Not Authorized to access this project")
    
    query_vector = generate_text_embedding(query)

    if not query_vector:
        raise HTTPException(status_code=500,detail="Failed to generate embedding for the search query")
    
    chunks = session.exec(select(ProjectChunk).where(ProjectChunk.pdf_id == pdf_id)).all()

    if not chunks:
        raise HTTPException(status_code=404, detail="No processed chunks found for this PDF.")
    
    search_results = []

    for chunk in chunks:
        if not chunk.embedding:
            continue

        chunk_vector = json.loads(chunk.embedding)
        similarity_score = calculate_cosine_similarity(query_vector,chunk_vector)

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

@app.post("/projects/{project_id}/pdfs/{pdf_id}/chat")
def chat_with_pdf(
    project_id: int,
    pdf_id: int,
    question: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    
    project = session.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")


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
        .limit(6)  # Grab the last 3 turns (3 user questions, 3 AI answers)
    ).all()

    past_messages.reverse()

    history_context = ""
    for msg in past_messages:
        history_context += f"{msg.sender.upper()}: {msg.message_text}\n"

    llm_output = generate_llm_answer_with_memory(question, top_context_texts, history_context)
    ai_answer = llm_output.get("answer", "")
    suggested_followups = llm_output.get("suggested_followups", [])

    user_record = ChatMessage(sender="user",message_text=question,pdf_id=pdf_id)
    ai_record = ChatMessage(sender="ai",message_text=ai_answer ,pdf_id=pdf_id)

    session.add(user_record)
    session.add(ai_record)
    session.commit()

    return {
        "question": question,
        "answer": ai_answer,
        "sources_used": len(top_context_texts),
        "suggested_followups" : suggested_followups,
        "citations": [
            {
                "index": i, 
                "page": item[2], 
                "text_snippet": item[1][:150] + "..."
            } 
            for i, item in enumerate(top_context)
        ]
    }
   
@app.get("/projects/{project_id}/pdfs/{pdf_id}/history")
def get_chat_history(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    project = session.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project's history")

    pdf_record = session.get(ProjectPDF, pdf_id)
    if not pdf_record or pdf_record.project_id != project_id:
        raise HTTPException(status_code=404, detail="PDF record not found in this project")

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

@app.post("/projects/{project_id}/pdfs/{pdf_id}/summary")
def get_pdf_summary(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    project = session.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    
    pdf_record = session.get(ProjectPDF, pdf_id)
    if not pdf_record or pdf_record.project_id != project_id:
        raise HTTPException(status_code=404, detail="PDF record not found in this project")
    
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

@app.post("/projects/{project_id}/pdfs/{pdf_id}/notes")
def get_pdf_notes(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    project = session.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    
    pdf_record = session.get(ProjectPDF, pdf_id)
    if not pdf_record or pdf_record.project_id != project_id:
        raise HTTPException(status_code=404, detail="PDF record not found in this project")

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

@app.post("/projects/{project_id}/pdfs/{pdf_id}/flashcards")
def get_pdf_flashcards(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    
    project = session.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")

    pdf_record = session.get(ProjectPDF, pdf_id)
    if not pdf_record or pdf_record.project_id != project_id:
        raise HTTPException(status_code=404, detail="PDF record not found in this project")

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

@app.post("/projects/{project_id}/pdfs/{pdf_id}/quiz")
def get_pdf_quiz(
    project_id: int,
    pdf_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Project Authorization Check
    project = session.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")

    # 2. PDF Validity Check
    pdf_record = session.get(ProjectPDF, pdf_id)
    if not pdf_record or pdf_record.project_id != project_id:
        raise HTTPException(status_code=404, detail="PDF record not found in this project")
    
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