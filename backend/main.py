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
        extracted_text = ""

        for page_num,page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                extracted_text += f"--- Page {page_num + 1} ---\n{text}\n"

    except Exception as e:
        raise HTTPException(status_code=500,detail=f"Failed to parse  the pdf document: {str(e)}")
    
    cleaned_text = clean_extracted_text(extracted_text)
    if not cleaned_text:
            raise HTTPException(status_code=400, detail="The PDF contains no readable text extract.")
    
    text_chunks = chunk_text(cleaned_text,chunk_size=500,chunk_overlap=50)

    stored_chunks_response = []
    for index , chunk_payload in enumerate(text_chunks):

        vector_list = generate_text_embedding(chunk_payload)

        db_chunk = ProjectChunk(
            chunk_index=index,
            text_content=chunk_payload,
            embedding=json.dumps(vector_list),
            pdf_id=pdf_record.id
        )
        session.add(db_chunk)
        stored_chunks_response.append(db_chunk)

    session.commit()
    
    return {
        "message": "PDF Parsed, split , chunked database records generated successfully!",
        "pdf_id" : pdf_record.id,
        "filename" : pdf_record.filename,
        "total_pages" : len(reader.pages),
        "total_chunks_created": len(stored_chunks_response),
        "chunks": stored_chunks_response
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


