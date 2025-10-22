from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
import os
import re

app = FastAPI(title="Invoice Reader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# DeepSeek API konfiguracija
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_OCR_URL = "https://api.deepseek.com/ocr"

@app.get("/")
async def root():
    return {"message": "Invoice Reader API is working!"}

@app.post("/upload-invoice")
async def upload_invoice(file: UploadFile = File(...)):
    try:
        if not file.content_type.startswith(('image/', 'application/pdf')):
            raise HTTPException(400, "Fajl mora biti slika (JPEG, PNG) ili PDF")
        
        # Pročitaj fajl
        contents = await file.read()
        
        # Pozovi DeepSeek OCR API
        ocr_result = await process_with_deepseek(contents, file.content_type, file.filename)
        
        # Proveri da li je OCR uspešan
        if "error" in ocr_result:
            # Vrati test podatke ako OCR ne radi
            return JSONResponse({
                "status": "ocr_failed",
                "message": f"OCR greška: {ocr_result['error']}",
                "extracted_data": {
                    "invoice_number": "TEST-001",
                    "date": "2024-01-15",
                    "total_amount": "15.000,00 RSD",
                    "vendor_name": "Test Company DOO",
                    "raw_text": "OCR not available - using test data"
                }
            })
        
        # Ekstrahuj podatke iz fakture
        extracted_data = extract_invoice_data(ocr_result)
        
        return JSONResponse({
            "status": "success",
            "filename": file.filename,
            "extracted_data": extracted_data
        })
        
    except Exception as e:
        # Fallback na test podatke ako nešto pukne
        return JSONResponse({
            "status": "error_fallback",
            "message": f"Greška: {str(e)}",
            "extracted_data": {
                "invoice_number": "FALLBACK-001",
                "date": "2024-01-01",
                "total_amount": "10.000,00 RSD",
                "vendor_name": "Fallback Company",
                "raw_text": "Error occurred - fallback data"
            }
        })

async def process_with_deepseek(file_content: bytes, content_type: str, filename: str):
    """Poziva DeepSeek OCR API - pojednostavljena verzija"""
    if not DEEPSEEK_API_KEY:
        return {"error": "API_KEY_NOT_SET"}
    
    # Pojednostavljena verzija - šaljemo raw fajl
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    }
    
    files = {
        'file': (filename, file_content, content_type)
    }
    
    try:
        response = requests.post(
            DEEPSEEK_OCR_URL,
            headers=headers,
            files=files,
            timeout=30
        )
        
        print(f"DeepSeek API Status: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API error {response.status_code}"}
            
    except Exception as e:
        return {"error": f"Connection error: {str(e)}"}

def extract_invoice_data(ocr_result):
    """Ekstrahuje podatke iz OCR rezultata"""
    # Ako OCR ne radi, vrati test podatke
    if "error" in ocr_result:
        return {
            "invoice_number": "OCR-FAILED",
            "date": "N/A",
            "total_amount": "N/A",
            "vendor_name": "N/A",
            "raw_text": "OCR processing failed"
        }
    
    text = extract_text_from_ocr(ocr_result)
    
    extracted = {
        "invoice_number": find_invoice_number(text),
        "date": find_date(text),
        "total_amount": find_total_amount(text),
        "vendor_name": find_vendor_name(text),
        "raw_text": text[:500] + "..." if len(text) > 500 else text
    }
    
    return extracted

def extract_text_from_ocr(ocr_result):
    """Ekstrahuje tekst iz OCR rezultata"""
    if isinstance(ocr_result, str):
        return ocr_result
    elif 'text' in ocr_result:
        return ocr_result['text']
    elif 'results' in ocr_result and isinstance(ocr_result['results'], list):
        return ' '.join([item.get('text', '') for item in ocr_result['results']])
    else:
        return str(ocr_result)

def find_invoice_number(text):
    import re
    patterns = [
        r'Faktura[:\s]*([A-Z0-9-]+)',
        r'Invoice[:\s]*([A-Z0-9-]+)',
        r'Broj[:\s]*([A-Z0-9-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return "Nije pronađen"

def find_date(text):
    import re
    date_pattern = r'\d{1,2}[./]\d{1,2}[./]\d{2,4}'
    match = re.search(date_pattern, text)
    return match.group(0) if match else "Nije pronađen"

def find_total_amount(text):
    import re
    patterns = [
        r'UKUPNO[:\s]*([0-9.,]+)',
        r'TOTAL[:\s]*([0-9.,]+)',
        r'Za uplatu[:\s]*([0-9.,]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return "Nije pronađen"

def find_vendor_name(text):
    lines = text.split('\n')
    for line in lines[:5]:
        line = line.strip()
        if line and len(line) > 3:
            return line
    return "Nije pronađen"

@app.get("/test")
async def test_endpoint():
    return {"message": "Test uspešan! API radi."}

@app.get("/api-status")
async def api_status():
    return {
        "deepseek_api_key_set": bool(DEEPSEEK_API_KEY),
        "api_key_preview": DEEPSEEK_API_KEY[:8] + "..." if DEEPSEEK_API_KEY else "Not set",
        "status": "ready"
    }
