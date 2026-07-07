from fastapi import FastAPI,HTTPException,Depends
from sqlmodel import SQLModel,create_engine,Field,Session,select
from pydantic import EmailStr

class User(SQLModel,table=True):
    id: int | None = Field(default=None,primary_key=True)
    username: str = Field(unique=True,index=True)
    email : str = Field(unique=True)
    password : str 

class UserCreate(SQLModel): #this helps to user enter these things
    username: str
    email: EmailStr
    password: str


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

#this talks to database
engine = create_engine(sqlite_url,connect_args={"check_same_thread" : False})


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():  #to open and close DB
    with Session(engine) as session:
        yield session

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
    
    new_user = User(
        username=user_data.username,
        email = user_data.email,
        password = user_data.password
    )

    session.add(new_user)
    session.commit()
    session.refresh(new_user)

