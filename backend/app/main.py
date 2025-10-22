from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
import os
import re
import base64

app = FastAPI(title="Invoice Reader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# DeepSeek API konfiguracija
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_OCR_URL = "https://api.deepseek.com/ocr"  # Proverite tačan URL

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
        ocr_result = await process_with_deepseek(contents, file.content_type)
        
        # Proveri da li je OCR uspešan
        if "error" in ocr_result:
            return JSONResponse({
                "status": "error",
                "message": f"OCR greška: {ocr_result['error']}",
                "extracted_data": {
                    "invoice_number": "OCR_FAILED",
                    "date": "OCR_FAILED",
                    "total_amount": "OCR_FAILED", 
                    "vendor_name": "OCR_FAILED",
                    "raw_text": "OCR processing failed"
                }
            })
        
        # Ekstrahuj podatke iz fakture
        extracted_data = extract_invoice_data(ocr_result)
        
        return JSONResponse({
            "status": "success",
            "filename": file.filename,
            "extracted_data": extracted_data,
            "ocr_debug": ocr_result  # Za debugging
        })
        
    except Exception as e:
        raise HTTPException(500, f"Greška pri obradi: {str(e)}")

async def process_with_deepseek(file_content: bytes, content_type: str):
    """Poziva DeepSeek OCR API"""
    if not DEEPSEEK_API_KEY:
        return {"error": "API_KEY_NOT_SET"}
    
    # Konvertuj u base64 za slike
    if content_type.startswith('image/'):
        base64_image = base64.b64encode(file_content).decode('utf-8')
        payload = {
            "image": f"data:{content_type};base64,{base64_image}"
        }
    else:
        # Za PDF fajlove
        payload = {
            "file": base64.b64encode(file_content).decode('utf-8')
        }
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            DEEPSEEK_OCR_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"DeepSeek API Response: {response.status_code}")  # Debug
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API error {response.status_code}: {response.text}"}
            
    except Exception as e:
        return {"error": f"Connection error: {str(e)}"}

def extract_invoice_data(ocr_result):
    """Ekstrahuje podatke iz OCR rezultata"""
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
    if 'text' in ocr_result:
        return ocr_result['text']
    elif 'results' in ocr_result and isinstance(ocr_result['results'], list):
        return ' '.join([item.get('text', '') for item in ocr_result['results']])
    elif 'data' in ocr_result and 'text' in ocr_result['data']:
        return ocr_result['data']['text']
    else:
        return str(ocr_result)

def find_invoice_number(text):
    import re
    patterns = [
        r'Faktura[:\s]*([A-Z0-9-]+)',
        r'Invoice[:\s]*([A-Z0-9-]+)',
        r'Broj[:\s]*([A-Z0-9-]+)',
        r'Br[.\s]*([A-Z0-9-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return "Nije pronađen"

def find_date(text):
    import re
    date_patterns = [
        r'\d{1,2}[./]\d{1,2}[./]\d{2,4}',
        r'\d{4}-\d{2}-\d{2}'
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return "Nije pronađen"

def find_total_amount(text):
    import re
    patterns = [
        r'UKUPNO[:\s]*([0-9.,]+)',
        r'TOTAL[:\s]*([0-9.,]+)',
        r'Za uplatu[:\s]*([0-9.,]+)',
        r'Iznos[:\s]*([0-9.,]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return "Nije pronađen"

def find_vendor_name(text):
    lines = text.split('\n')
    for line in lines[:10]:
        line = line.strip()
        if line and len(line) > 3 and not any(word in line.lower() for word in ['faktura', 'invoice', 'datum']):
            return line
    return "Nije pronađen"

@app.get("/test")
async def test_endpoint():
    return {"message": "Test uspešan! API radi."}

@app.get("/api-status")
async def api_status():
    return {
        "deepseek_api_key_set": bool(DEEPSEEK_API_KEY),
        "api_key_preview": DEEPSEEK_API_KEY[:8] + "..." if DEEPSEEK_API_KEY else "Not set"
    }
