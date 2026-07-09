from fastapi import FastAPI,HTTPException,Depends,File,UploadFile
from sqlmodel import SQLModel,create_engine,Field,Session,select
from pydantic import EmailStr
from datetime import datetime,timedelta,timezone
from fastapi.security import OAuth2PasswordBearer,OAuth2PasswordRequestForm
from pypdf import PdfReader
import bcrypt
import jwt
import os

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
    
    return {
        "pdf_id" : pdf_record.id,
        "filename" : pdf_record.filename,
        "total_pages" : len(reader.pages),
        "content" : extracted_text
    }
