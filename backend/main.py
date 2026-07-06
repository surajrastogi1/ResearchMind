from fastapi import FastAPI

app = FastAPI(title="ResearchMind")

@app.get("/")
def root():
    return {"message" : "Welcome to ResearchMind"}

