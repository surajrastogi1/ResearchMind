# 🧠 ResearchMind

> An AI-powered research assistant that helps you understand, analyze, and learn from PDF documents.

## 📌 Overview

**ResearchMind** is an AI-powered document research and learning platform that allows users to upload PDF documents and interact with them using AI.

Instead of manually reading through large documents, users can upload a PDF and use ResearchMind to **ask questions, generate summaries, create study notes, flashcards, and quizzes** based on the document's content.

The project combines **AI, semantic search, document processing, and a modern Backend architecture** to create an interactive research experience.

## ✨ Features

* 📄 **PDF Upload** — Upload research papers, notes, books, or other PDF documents.
* 💬 **Chat with PDF** — Ask questions and get AI-generated answers based on the uploaded document.
* 📝 **AI Summaries** — Generate concise summaries from uploaded documents.
* 📚 **Study Notes** — Convert document content into structured notes.
* 🧠 **Flashcards** — Generate flashcards to help with revision and learning.
* ❓ **AI Quizzes** — Generate quizzes based on the document's content.
* 🔍 **Semantic Search** — Find relevant information using embeddings and similarity search.
* 🔐 **Authentication** — Secure user authentication using JWT.
* 🤖 **AI-Powered Responses** — Uses Google's Gemini models for text generation and embeddings.

## 🏗️ Architecture

```text
                    ┌─────────────────┐
                    │     FastAPI     │
                    │     Backend     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌───────────┐  ┌────────────┐  ┌───────────┐
        │ PDF Parser│  │ Gemini AI  │  │ Database  │
        │           │  │            │  │           │
        └───────────┘  └────────────┘  └───────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Embeddings &  │
                    │ Semantic Search │
                    └─────────────────┘
```

## 🛠️ Tech Stack

### Backend

* FastAPI
* Python
* Pydantic
* SQLModel

### AI / Machine Learning

* Google Gemini
* Text Embeddings
* Cosine Similarity
* Semantic Search

### Database

* SQLite (development)

### Authentication

* JWT
* OAuth2
* bcrypt

### PDF Processing

* PyPDF / PdfReader

## ⚙️ How It Works

### 1. Upload a PDF

The user uploads a PDF document through the application.

### 2. Extract Text

ResearchMind extracts the text from the PDF and processes the document.

### 3. Split Into Chunks

The extracted content is divided into smaller chunks so that the AI can efficiently process the document.

### 4. Generate Embeddings

Embeddings are generated for the document chunks using an AI embedding model.

### 5. Semantic Search

When the user asks a question, ResearchMind compares the question with the document embeddings using **cosine similarity** to find the most relevant sections.

### 6. Generate the Answer

The relevant document content is provided to the Gemini model, which generates an answer based on the retrieved information.

```text
PDF
 │
 ▼
Text Extraction
 │
 ▼
Text Chunking
 │
 ▼
Embeddings
 │
 ▼
Vector/Semantic Search
 │
 ▼
Relevant Context
 │
 ▼
Gemini
 │
 ▼
AI Response
```

## 🚀 Getting Started

### Prerequisites

Make sure you have installed:

* Python 3.10+
* Git

You also need a Google Gemini API key.

### Clone the Repository

```bash
git clone https://github.com/your-username/researchmind.git

cd researchmind
```

## 🔧 Backend Setup

Navigate to the backend:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
SECRET_KEY=your_secret_key
DATABASE_URL=your_database_url
```

Start the FastAPI server:

```bash
uvicorn main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

FastAPI documentation:

```text
http://localhost:8000/docs
```


## 🧪 Example Use Case

Imagine you have a **50-page research paper**.

Instead of reading the entire document to find a specific piece of information:

```text
Upload Research Paper
        ↓
Ask:
"What methodology did the researchers use?"
        ↓
ResearchMind searches the document
        ↓
Finds relevant sections
        ↓
Gemini generates an answer
```

You can also generate:

* 📋 Summary
* 📝 Notes
* 🧠 Flashcards
* ❓ Quiz questions

from the same document.

## 🔮 Future Improvements

* [ ] PostgreSQL production database
* [ ] Persistent vector database
* [ ] Multiple PDF support
* [ ] Conversation history
* [ ] Better document citations
* [ ] Source highlighting
* [ ] Streaming AI responses
* [ ] Document comparison
* [ ] Web research integration
* [ ] Advanced RAG pipeline
* [ ] User dashboard
* [ ] Deployment with Docker
* [ ] Production deployment

## 🎯 Learning Goals

ResearchMind was built to gain practical experience with:

* Backend application development
* REST API development
* FastAPI
* Authentication
* Database design
* PDF processing
* Embeddings
* Semantic search
* Retrieval-Augmented Generation (RAG)
* Generative AI
* Connecting AI models with real-world applications

## 👨‍💻 Author

**Suraj Rastogi**

Built as a hands-on project to explore **AI + Backend Application**.

## ⭐ Support

If you find this project interesting, consider giving the repository a ⭐ on GitHub.

---

**ResearchMind — Turn documents into knowledge. 🧠**
