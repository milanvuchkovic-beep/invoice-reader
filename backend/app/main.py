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
            raise HTTPException(400, "Fajl mora biti slika (JPEG, PNG) ili PDF")
        
        # Pročitaj fajl
        contents = await file.read()
        
        # Pozovi DeepSeek Vision API za OCR
        ocr_result = await process_with_deepseek_vision(contents, file.content_type)
        
        # Proveri da li je OCR uspešan
        if "error" in ocr_result:
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
            "extracted_data": extracted_data,
            "ocr_raw_text": ocr_result.get("text", "")[:200] + "..."  # Samo prvi deo za debug
        })
        
    except Exception as e:
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

async def process_with_deepseek_vision(file_content: bytes, content_type: str):
    """Koristi DeepSeek Vision API za OCR"""
    if not DEEPSEEK_API_KEY:
        return {"error": "API_KEY_NOT_SET"}
    
    # Konvertuj u base64
    base64_data = base64.b64encode(file_content).decode('utf-8')
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Kreiraj prompt specijalno za fakture
    prompt = """
    EXTRAHUJ SAV TEKST SA OVE SLIKE FAKTURE. Vrati samo sirovi tekst bez ikakvog formatiranja, bez komentara, bez markdown. 
    Fokusiraj se na: broj fakture, datum, ukupan iznos, ime dobavljača.
    
    Tekst:
    """
    
    # Napravi payload za vision model
    if content_type.startswith('image/'):
        payload = {
            "model": "deepseek-chat",  # Ili "deepseek-vision" ako postoji
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
            "max_tokens": 2000,
            "stream": False
        }
    else:
        # Za PDF fajlove - koristimo samo tekst
        return {"error": "PDF not yet supported - use images for now"}
    
    try:
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"DeepSeek API Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                text_content = data["choices"][0]["message"]["content"]
                return {"text": text_content}
            else:
                return {"error": "No text content in response"}
        else:
            error_detail = response.text
            print(f"DeepSeek API Error: {response.status_code} - {error_detail}")
            return {"error": f"API error {response.status_code}: {error_detail}"}
            
    except Exception as e:
        print(f"DeepSeek Connection Error: {str(e)}")
        return {"error": f"Connection error: {str(e)}"}

def extract_invoice_data(ocr_result):
    """Ekstrahuje podatke iz OCR rezultata"""
    if "error" in ocr_result:
        return {
            "invoice_number": "OCR-FAILED",
            "date": "N/A",
            "total_amount": "N/A", 
            "vendor_name": "N/A",
            "raw_text": "OCR processing failed"
        }
    
    text = ocr_result.get("text", "")
    
    extracted = {
        "invoice_number": find_invoice_number(text),
        "date": find_date(text),
        "total_amount": find_total_amount(text),
        "vendor_name": find_vendor_name(text),
        "raw_text": text[:500] + "..." if len(text) > 500 else text
    }
    
    return extracted

def find_invoice_number(text):
    import re
    patterns = [
        r'Faktura[:\s]*([A-Z0-9-]+)',
        r'Invoice[:\s]*([A-Z0-9-]+)',
        r'Broj[:\s]*([A-Z0-9-]+)',
        r'Br[.\s]*([A-Z0-9-]+)',
        r'FAKTURA[\s]*([A-Z0-9-]+)'
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
        r'\d{4}-\d{2}-\d{2}',
        r'\d{1,2}\s+[a-zA-Z]+\s+\d{4}'
    ]
    for pattern in date_patterns:
        matches = re.findall(pattern, text)
        if matches:
            return matches[0]  # Vrati prvi pronađeni datum
    return "Nije pronađen"

def find_total_amount(text):
    import re
    patterns = [
        r'UKUPNO[:\s]*([0-9.,]+\s*(?:RSD|EUR|USD|€|\$)?)',
        r'TOTAL[:\s]*([0-9.,]+\s*(?:RSD|EUR|USD|€|\$)?)',
        r'Za uplatu[:\s]*([0-9.,]+\s*(?:RSD|EUR|USD|€|\$)?)',
        r'Iznos[:\s]*([0-9.,]+\s*(?:RSD|EUR|USD|€|\$)?)',
        r'SUM[A]?[:\s]*([0-9.,]+\s*(?:RSD|EUR|USD|€|\$)?)'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return "Nije pronađen"

def find_vendor_name(text):
    lines = text.split('\n')
    for line in lines[:10]:  # Gledaj prvih 10 linija
        line = line.strip()
        if (line and len(line) > 3 and 
            not any(word in line.lower() for word in ['faktura', 'invoice', 'datum', 'date', 'ukupno', 'total']) and
            not re.match(r'^\d+[./]\d+[./]\d+$', line) and  # Nije datum
            not re.match(r'^[0-9.,]+\s*(?:RSD|EUR|USD)?$', line)):  # Nije iznos
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
        "api_url": DEEPSEEK_API_URL,
        "status": "ready"
    }

@app.get("/test-simple")
async def test_simple_ocr():
    """Testira DeepSeek API sa jednostavnim tekstom"""
    if not DEEPSEEK_API_KEY:
        return {"error": "API_KEY_NOT_SET"}
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "Reci mi samo 'TEST USPESAN'"}
        ],
        "max_tokens": 10,
        "stream": False
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {"status": "success", "response": data}
        else:
            return {"status": "error", "code": response.status_code, "detail": response.text}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
