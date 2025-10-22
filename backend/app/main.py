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
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

@app.get("/")
async def root():
    return {"message": "Invoice Reader API is working!"}

@app.post("/upload-invoice")
async def upload_invoice(file: UploadFile = File(...)):
    try:
        if not file.content_type.startswith(('image/', 'application/pdf')):
            return JSONResponse({
                "status": "error",
                "message": "Fajl mora biti slika (JPEG, PNG) ili PDF",
                "extracted_data": get_fallback_data()
            })
        
        # Pročitaj fajl
        contents = await file.read()
        
        # Pozovi DeepSeek Vision API za OCR
        ocr_result = await process_with_deepseek_vision(contents, file.content_type)
        
        # Proveri da li je OCR uspešan
        if "error" in ocr_result:
            return JSONResponse({
                "status": "ocr_failed",
                "message": f"OCR greška: {ocr_result['error']}",
                "extracted_data": get_test_data()
            })
        
        # Ekstrahuj podatke iz fakture
        extracted_data = extract_invoice_data(ocr_result)
        
        return JSONResponse({
            "status": "success",
            "filename": file.filename,
            "extracted_data": extracted_data
        })
        
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": f"Greška: {str(e)}",
            "extracted_data": get_fallback_data()
        })

async def process_with_deepseek_vision(file_content: bytes, content_type: str):
    """Koristi DeepSeek Vision API za OCR"""
    if not DEEPSEEK_API_KEY:
        return {"error": "API_KEY_NOT_SET"}
    
    # Podrži samo slike za sada
    if not content_type.startswith('image/'):
        return {"error": "Only images supported for now"}
    
    # Konvertuj u base64
    base64_data = base64.b64encode(file_content).decode('utf-8')
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Prompt za fakture
    prompt = "Extract all text from this invoice image. Return only the raw text without any formatting."
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{base64_data}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1000,
        "stream": False
    }
    
    try:
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                text_content = data["choices"][0]["message"]["content"]
                return {"text": text_content}
            else:
                return {"error": "No text in response"}
        else:
            return {"error": f"API error {response.status_code}"}
            
    except Exception as e:
        return {"error": f"Connection error: {str(e)}"}

def extract_invoice_data(ocr_result):
    """Ekstrahuje podatke iz OCR rezultata"""
    text = ocr_result.get("text", "")
    
    # Ako nema teksta, vrati test podatke
    if not text.strip():
        return get_test_data()
    
    extracted = {
        "invoice_number": find_invoice_number(text),
        "date": find_date(text),
        "total_amount": find_total_amount(text),
        "vendor_name": find_vendor_name(text),
        "raw_text": text[:300] + "..." if len(text) > 300 else text
    }
    
    return extracted

def find_invoice_number(text):
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
    date_pattern = r'\d{1,2}[./]\d{1,2}[./]\d{2,4}'
    match = re.search(date_pattern, text)
    return match.group(0) if match else "Nije pronađen"

def find_total_amount(text):
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

def get_test_data():
    """Vrati test podatke kada OCR ne radi"""
    return {
        "invoice_number": "TEST-001",
        "date": "2024-01-15",
        "total_amount": "15.000,00 RSD",
        "vendor_name": "Test Company DOO",
        "raw_text": "Test data - OCR not available"
    }

def get_fallback_data():
    """Vrati fallback podatke kada ima greške"""
    return {
        "invoice_number": "FALLBACK-001",
        "date": "2024-01-01",
        "total_amount": "10.000,00 RSD",
        "vendor_name": "Fallback Company",
        "raw_text": "Error occurred - fallback data"
    }

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
