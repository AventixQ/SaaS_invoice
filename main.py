import os
import re
from fastapi import FastAPI, UploadFile, File, HTTPException
import boto3

app = FastAPI()


def get_textract_client():
    return boto3.client(
        "textract",
        region_name="us-east-1",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
    )


def normalize_amount(value: str) -> float:
    if not value:
        return 0.0
    cleaned = value.replace(" ", "").replace(",", ".")
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def extract_nip_from_text(text: str) -> str:
    match = re.search(r"\b\d{3}[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}\b", text)
    if match:
        return re.sub(r"\D", "", match.group())
    return ""


def extract_largest_amount(text: str) -> float:
    amounts = re.findall(r"\d+[.,]\d{2}", text)
    values = [normalize_amount(a) for a in amounts]
    return max(values) if values else 0.0


@app.post("/invoice")
async def analyze_invoice(file: UploadFile = File(...)):
    try:
        client = get_textract_client()
        file_bytes = await file.read()

        response = client.analyze_expense(
            Document={"Bytes": file_bytes}
        )

        result = {
            "vat_id": "",
            "address": "",
            "total": 0.0
        }

        if not response.get("ExpenseDocuments"):
            return result

        doc = response["ExpenseDocuments"][0]
        summary_fields = doc.get("SummaryFields", [])

        full_text_parts = []

        for field in summary_fields:
            field_type = field.get("Type", {}).get("Text", "")
            field_value = field.get("ValueDetection", {}).get("Text", "")

            if field_value:
                full_text_parts.append(field_value)

            if field_type in ["VENDOR_TAX_ID", "TAX_ID"]:
                result["vat_id"] = re.sub(r"\D", "", field_value)

            elif field_type in ["VENDOR_ADDRESS", "ADDRESS"]:
                result["address"] = field_value

            elif field_type == "TOTAL":
                result["total"] = normalize_amount(field_value)

        full_text = " ".join(full_text_parts)

        if not result["vat_id"]:
            result["vat_id"] = extract_nip_from_text(full_text)

        if result["total"] == 0.0:
            result["total"] = extract_largest_amount(full_text)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
