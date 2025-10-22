from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
import os
import re

app = FastAPI(title="Invoice Reader API")

# CORS za frontend komunikaciju
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# DeepSeek API konfiguracija - OVO ĆEMO KASNIJE PODEŠAVATI
DEEPSEEK_API_KEY = "your_api_key_here"
DEEPSEEK_OCR_URL = "https://api.deepseek.com/v1/ocr"

@app.get("/")
async def root():
    return {"message": "Invoice Reader API is working!"}

@app.post("/upload-invoice")
async def upload_invoice(file: UploadFile = File(...)):
    try:
        # Provera tipa fajla
        if not file.content_type.startswith(('image/', 'application/pdf')):
            raise HTTPException(400, "Fajl mora biti slika (JPEG, PNG) ili PDF")
        
        # Simuliramo OCR proces dok ne podesimo pravi API
        simulated_data = {
            "invoice_number": "TEST-001",
            "date": "2024-01-15", 
            "total_amount": "15.000,00 RSD",
            "vendor_name": "Test Company DOO",
            "status": "simulated_data"
        }
        
        return JSONResponse({
            "status": "success",
            "filename": file.filename,
            "message": "API je spreman! DeepSeek OCR ćemo podesiti kasnije.",
            "extracted_data": simulated_data
        })
        
    except Exception as e:
        raise HTTPException(500, f"Greška pri obradi: {str(e)}")

@app.get("/test")
async def test_endpoint():
    return {"message": "Test uspešan! API radi."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
