from fastapi import HTTPException
from google import genai
import json
import math
import os

def _get_client() -> genai.Client:
    """Internal helper to initialize the GenAI Client with your exact API key string restriction."""
    api_key = os.getenv("GEMINI_API_Key")
    if not api_key:
        raise HTTPException(status_code=500, detail="CRITICAL: GEMINI_API_Key is missing from .env environment.")
    return genai.Client(api_key=api_key)

def generate_text_embedding(text: str) -> list[float]:
    if not text:
        return []
        
    client = _get_client()
        
    
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

    client = _get_client()
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
    client = _get_client()
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
    client = _get_client()
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
    client = _get_client()
    
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
    client = _get_client()
    
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

def extract_pdf_keywords(filename: str, context_chunks: list[str]) -> list[dict]:
    """Analyzes text chunks to extract the most statistically and contextually significant keywords."""
    client = _get_client()
    
    full_text = "\n".join(context_chunks[:25])
    
    system_prompt = (
        "You are an expert Text Analytics Engine. Analyze the provided document text and extract "
        "the top 5 to 7 most important keywords or technical key phrases.\n\n"
        "CRITICAL: You must return your response in raw JSON format matching this schema layout:\n"
        "[\n"
        "  {\n"
        "    \"keyword\": \"The specific word or short phrase...\",\n"
        "    \"relevance_score\": 0.95,\n"
        "    \"context_definition\": \"A brief 1-sentence explanation of how this term applies to the document.\"\n"
        "  }\n"
        "]\n"
        "Note: 'relevance_score' should be a float between 0.00 and 1.00 based on its thematic significance."
    )
    
    user_prompt = f"Document Filename: {filename}\n\nContent Pool:\n{full_text}"
    
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
        raise HTTPException(status_code=500, detail=f"Keyword Extraction Error: {str(e)}")

def classify_pdf_topic(filename: str, context_chunks: list[str]) -> dict:
    """Analyzes text chunks to determine the primary industry/academic category of the document."""
    client = _get_client()
    
    full_text = "\n".join(context_chunks[:25])
    
    system_prompt = (
        "You are an advanced Text Classification Model. Analyze the provided document text "
        "and determine its primary domain category.\n\n"
        "CRITICAL: You must return your response in raw JSON format matching this schema:\n"
        "{\n"
        "  \"primary_topic\": \"The main category name (e.g., Technology, Finance, Legal, Health, Education, etc...)\",\n"
        "  \"confidence_score\": 0.92,\n"
        "  \"reasoning\": \"A short 1-sentence explanation of why the document falls under this topic classification.\"\n"
        "}\n"
        "Note: 'confidence_score' must be a float between 0.00 and 1.00."
    )
    
    user_prompt = f"Document Filename: {filename}\n\nContent Pool:\n{full_text}"
    
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
        raise HTTPException(status_code=500, detail=f"Topic Classification Error: {str(e)}")

def cluster_project_documents(pdf_list: list[dict]) -> dict:
    """Analyzes a list of PDFs and their metadata to group them into clusters."""
    client = _get_client()
    
    system_prompt = (
        "You are a Machine Learning Data Engineer. Your task is to perform text clustering "
        "on the list of provided project documents.\n\n"
        "CRITICAL: Return a raw JSON object matching this schema:\n"
        "{\n"
        "  \"clusters\": [\n"
        "    {\n"
        "      \"cluster_id\": 0,\n"
        "      \"cluster_name\": \"Marketing & Branding\",\n"
        "      \"pdf_ids\": [1, 4]\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Group similar documents together based on their titles and contents. Every PDF must belong to a cluster."
    )
    
    user_prompt = f"Documents to cluster:\n{json.dumps(pdf_list, indent=2)}"
    
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
        raise HTTPException(status_code=500, detail=f"Clustering Error: {str(e)}")

def generate_pdf_recommendations(target_pdf: dict, other_pdfs: list[dict]) -> list[dict]:
    """Uses gemini-2.5-flash to discover contextually similar documents within the same project."""
    client = _get_client()
    
    system_prompt = (
        "You are an AI Recommendation Engine. Analyze the target document details and compare "
        "them against the alternative list of project documents to find the most contextually relevant matches.\n\n"
        "CRITICAL: You must return your response in raw JSON format matching this schema layout:\n"
        "[\n"
        "  {\n"
        "    \"pdf_id\": 2,\n"
        "    \"filename\": \"seo_guide.pdf\",\n"
        "    \"similarity_reasoning\": \"A short 1-sentence explanation of how this document relates to the target topic.\"\n"
        "  }\n"
        "]\n"
        "Return up to 3 recommendation objects, sorted from highest relevance to lowest. If no good match exists, return an empty array."
    )
    
    user_prompt = (
        f"Target Document:\n{json.dumps(target_pdf, indent=2)}\n\n"
        f"Available Documents to Recommend from:\n{json.dumps(other_pdfs, indent=2)}"
    )
    
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
        raise HTTPException(status_code=500, detail=f"Recommendation Error: {str(e)}")
