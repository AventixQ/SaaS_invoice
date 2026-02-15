import os
from fastapi import FastAPI, UploadFile, File, HTTPException
import boto3

app = FastAPI()

def get_textract_client():
    return boto3.client(
        'textract',
        region_name='us-east-1',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        aws_session_token=os.environ.get('AWS_SESSION_TOKEN')
    )

@app.post("/invoice")
async def analyze_invoice(file: UploadFile = File(...)):
    try:
        client = get_textract_client()
        file_bytes = await file.read()
        
        response = client.analyze_expense(Document={'Bytes': file_bytes})
        
        result = {"vat_id": "", "address": "", "total": 0.0}
        
        doc = response['ExpenseDocuments'][0]
        
        for field in doc['SummaryFields']:
            field_type = field.get('Type', {}).get('Text', '')
            field_value = field.get('ValueDetection', {}).get('Text', '')
            
            if field_type == 'TAX_Payer_ID':
                result["vat_id"] = field_value
            elif field_type == 'ADDRESS':
                result["address"] = field_value
            elif field_type == 'TOTAL':
                try:
                    result["total"] = float(field_value.replace(',', '.').replace(' ', ''))
                except:
                    pass
        
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))