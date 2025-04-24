from flask import Flask, request, jsonify, render_template
import uuid
import os
import pymupdf
import spacy
from spacy.tokens import Doc
import re
import pycountry
from typing import List, Set

app = Flask(__name__)
# Load spaCy NLP model for semantic analysis
nlp = spacy.load("en_core_web_sm")

# Temporary storage for uploaded PDFs (clean up after processing)
UPLOAD_FOLDER = "temp_uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Include your existing extraction functions here ---
# (Copy all functions from previous implementation: 
# extract_text_from_pdf, extract_title, extract_authors, 
# extract_year, extract_countries, etc.)


def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    import pymupdf  # PyMuPDF
    doc = pymupdf.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def extract_title(text: str) -> str:
    """Extract title from document text using structural and linguistic patterns"""
    # Clean the text and split into meaningful lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Common title patterns
    patterns = [
        # Title followed by author section
        r'(?i)^(.*?)(?=\n\s*(by|por|authors?|autores?)\b)',
        # Title in all caps with punctuation
        r'^([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9\s,.()-]{15,})(?=\s*[.!?]?\s*\n)',
        # Title ending with colon followed by subtitle
        r'^(.+?:)\s*\n',
        # Title followed by abstract/introduction markers
        r'(?i)^(.*?)(?=\n\s*(abstract|resumen|introduction|introducción))'
    ]
    
    # Check first 15 lines for title patterns
    for line in lines[:15]:
        # Skip common non-title elements
        if re.match(r'^\s*(doi|http|©|@)', line, re.I):
            continue
            
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                candidate = match.group(1).strip()
                # Validate candidate length and structure
                if 10 < len(candidate) < 300 and re.search(r'[a-zA-ZÁÉÍÓÚÑ]', candidate):
                    return candidate
                
    # Fallback 1: Longest line in first 10 lines that looks title-like
    candidates = sorted(
        [line for line in lines[:10] if 20 < len(line) < 250],
        key=len, 
        reverse=True
    )
    if candidates:
        return candidates[0]
    
    # Fallback 2: First sentence detection
    first_paragraph = re.sub(r'\s+', ' ', text.split('\n\n')[0])
    sentences = re.split(r'(?<=[.!?])\s+', first_paragraph)
    if sentences:
        return sentences[0][:300]
    
    return "Título no encontrado"

def extract_authors(text: str) -> List[str]:
    """Extract authors from articles in English and Spanish using regex and spaCy NER."""
    # Common patterns for author lists in English and Spanish
    author_patterns = [
        r"by\s+([A-Z][a-z]+ [A-Z][a-z]+(?:, | and )?)+",  # English: "By John Doe and Jane Smith"
        r"por\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+ [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:, | y )?)+",  # Spanish: "Por Juan Pérez y Ana López"
        r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:, [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)(?=\nAbstract|Resumen)",  # Authors before abstract/resumen
    ]
    
    authors = []
    for pattern in author_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_authors = match.group(1)
            # Split by commas, "and", "y", or semicolons
            authors = re.split(r', |; | and | y ', raw_authors)
            authors = [a.strip() for a in authors if a.strip()]
            break
    
    # Fallback: Use spaCy's NER to find person names
    if not authors:
        doc = nlp(text)
        authors = [ent.text for ent in doc.ents if ent.label_ == "PERSON"][:6]  # Limit to first 6 names
    
    return authors if authors else ["Autores no encontrados"]

def extract_year(text: str) -> str:
    """Extract publication year using regex near title/author section."""
    # Look for 4-digit years close to common keywords
    year_patterns = [
        r"(?:Año|Fecha de publicación|Fecha):?\s*(\d{4})",
        r"\b(19|20)\d{2}\b(?=.*\b(?:Abstract|Introduction|Resumen|Introducción)\b)"
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1) if match.groups() else match.group()
    # Fallback: Search entire text
    match = re.search(r'\b(19|20)\d{2}\b', text)
    return match.group() if match else "Year not found"

def is_valid_country(name: str) -> bool:
    """Verify if a string is a recognized country name using ISO standards"""
    try:
        return pycountry.countries.lookup(name) is not None
    except LookupError:
        return False

def extract_countries(doc: Doc) -> List[str]:
    """
    Extract validated country names from text using spaCy's NER
    with pycountry validation and ambiguity resolution
    """
    countries = []
    seen: Set[str] = set()
    
    for ent in doc.ents:
        if ent.label_ == "GPE":
            # Attempt direct match
            if is_valid_country(ent.text):
                clean_name = pycountry.countries.lookup(ent.text).name
                if clean_name not in seen:
                    countries.append(clean_name)
                    seen.add(clean_name)
                continue
                
            # Try common alternative names
            for country in pycountry.countries:
                if ent.text.lower() in map(str.lower, country.aliases):
                    if country.name not in seen:
                        countries.append(country.name)
                        seen.add(country.name)
                    break

    return sorted(countries) if countries else ["No countries found"]

def extract_publication_name(text: str) -> str:
    """Extract journal/conference name from headers or common patterns."""
    pub_patterns = [
        r"Proceedings of (the )?(.*?)\d{4}",
        r"Journal of (.*?)(\d|\(|$)",
        r"Revista (.*?)\d{4}",  # Matches "Revista ..." with a year
        r"Congreso (.*?)\d{4}",  # Matches "Congreso ..." with a year
        r"Actas del (.*?)\d{4}",  # Matches "Actas del ..." with a year
        r"Publicado en (.*?)\d{4}",  # Matches "Publicado en ..." with a year
        r"((?:IEEE|ACM|Springer) .*?(?:Conference|Journal|Symposium))"
    ]
    
    for pattern in pub_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return "Publicación no encontrada"

def extract_url_doi(text: str) -> str:
    """Extract URL or DOI from text."""
    doi_pattern = r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b"
    url_pattern = r"https?://[^\s]+"
    
    match = re.search(doi_pattern, text, re.IGNORECASE) or re.search(url_pattern, text)
    return 'https://doi.org/' + match.group() if match else "URL/DOI no encontrado"

def extract_abstract(text: str) -> str:
    """Extract abstract using regex-based section detection."""
    abstract_patterns = [
        r"Resumen\n([\s\S]+?)(?=Introducción|Palabras clave|§|\n\n)",
        r"Abstract\n([\s\S]+?)(?=Introducción|Palabras clave|§|\n\n)",
        r"Introducción\n([\s\S]+?)(?=1\. |§|\n\n)",
        r"Summary\n([\s\S]+?)(?=1\. )"
    ]
    
    for pattern in abstract_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return re.sub(r'\s+', ' ', match.group(1)).strip()
    return "Abstract/Resumen no encontrado"



def process_pdf(pdf_path: str) -> dict:
    """Wrapper function for PDF processing"""
    text = extract_text_from_pdf(pdf_path)
    doc = nlp(text)
    
    return {
        "title": extract_title(text),
        "authors": extract_authors(text),
        "year": extract_year(text),
        "countries": extract_countries(doc),
        "publication_name": extract_publication_name(text),
        "url_doi": extract_url_doi(text),
        "abstract": extract_abstract(text)
    }

@app.route('/')
def index():
    """Serve the index.html file"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_pdf():
    """API endpoint for PDF analysis"""
    # Validate file upload
    if 'pdf' not in request.files:
        return jsonify({"error": "No PDF file uploaded"}), 400
    
    pdf_file = request.files['pdf']
    if not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Invalid file type"}), 400

    temp_path = None  # Initialize temp_path to avoid NameError in case of an exception
    try:
        # Save uploaded file temporarily
        temp_filename = str(uuid.uuid4()) + ".pdf"
        temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
        pdf_file.save(temp_path)

        # Process PDF
        result = process_pdf(temp_path)
        
        # Clean up temporary file
        os.remove(temp_path)

        return jsonify(result)

    except Exception as e:
        # Clean up if error occurs
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
