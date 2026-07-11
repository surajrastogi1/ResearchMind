from sqlmodel import SQLModel,Field
from pydantic import EmailStr
from datetime import datetime,timezone

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