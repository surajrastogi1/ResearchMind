import re

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