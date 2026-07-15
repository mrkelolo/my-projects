import base64
import os
import uuid
import json
import logging
from typing import List, Tuple, Optional

import cv2
import numpy as np
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from easyocr import Reader
except ImportError:
    Reader = None

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from openai import OpenAI
import uvicorn

# ------------------------------------------------------------------
# 1. Logging configuration
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("invoice_pipeline")

# ------------------------------------------------------------------
# 2. Pydantic data models – JSON schema for the invoice
# ------------------------------------------------------------------
class InvoiceLineItem(BaseModel):
    description: str = Field(..., description="Description of the line item")
    quantity: float = Field(..., description="Quantity of items")
    unit_price: float = Field(..., description="Price per unit")
    tax_rate: Optional[float] = Field(None, description="Tax rate (e.g., 0.2 for 20%)")
    total_amount: float = Field(..., description="Total amount for this line item")

class InvoiceData(BaseModel):
    vendor_name: str = Field(..., description="Name of the vendor/supplier")
    vendor_address: str = Field(..., description="Address of the vendor")
    invoice_number: str = Field(..., description="Invoice number")
    invoice_date: str = Field(..., description="Date of the invoice (YYYY-MM-DD)")
    due_date: str = Field(..., description="Due date for payment (YYYY-MM-DD)")
    subtotal: float = Field(..., description="Subtotal before tax")
    tax_amount: float = Field(..., description="Total tax amount")
    total_amount: float = Field(..., description="Total invoice amount")
    currency: str = Field("USD", description="Currency code (e.g., USD, EUR)")
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    payment_terms: Optional[str] = Field(None, description="Payment terms")
    po_number: Optional[str] = Field(None, description="Purchase order number")
    notes: Optional[str] = Field(None, description="Additional notes")

# ------------------------------------------------------------------
# 3. Image preprocessing & OCR
# ------------------------------------------------------------------
def preprocess_image(image_path: str) -> np.ndarray:
    """Return a cleaned, deskewed grayscale image."""
    logger.debug(f"Preprocessing image: {image_path}")
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Unable to read image: {image_path}")

    # Denoise
    img = cv2.fastNlMeansDenoising(img, h=10)

    # Binarize
    _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Deskew
    coords = np.column_stack(np.where(img > 0))
    if coords.size == 0:
        return img
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    return img

def extract_ocr_text(image_path: str) -> Tuple[str, str]:
    """Run Tesseract and EasyOCR on the same image and return both results."""
    logger.debug(f"Extracting OCR text from: {image_path}")
    img = preprocess_image(image_path)

    # Temporary file for OCR
    temp_file = "_preprocessed.png"
    cv2.imwrite(temp_file, img)

    # Tesseract OCR
    try:
        tess_text = pytesseract.image_to_string(
            Image.open(temp_file),
            config="--psm 6 --oem 3"
        ).strip()
    except Exception as e:
        logger.error(f"Tesseract OCR failed: {e}")
        tess_text = ""

    # EasyOCR
    if Reader is not None:
        try:
            reader = Reader(['en'])
            easy_text = "\n".join([d[1] for d in reader.readtext(temp_file)]).strip()
        except Exception as e:
            logger.error(f"EasyOCR failed: {e}")
            easy_text = ""
    else:
        easy_text = ""

    os.remove(temp_file)
    return tess_text, easy_text

# ------------------------------------------------------------------
# 4. AI extraction (OpenAI GPT‑4o)
# ------------------------------------------------------------------
class InvoiceExtractor:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def _image_to_data_uri(self, image_path: str) -> str:
        """Return a data‑URI string for the image."""
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

    def extract(self, image_path: str, ocr_text: str) -> InvoiceData:
        """Ask GPT‑4o to parse the invoice and return structured JSON."""
        logger.info(f"Extracting invoice data from image: {image_path}")
        prompt = f"""
        You are an expert at reading invoices. Extract the following fields in exact JSON format:

        {json.dumps(InvoiceData.schema(), indent=2)}

        Provided OCR text:
        {ocr_text}

        If any field is missing in the invoice, set it to null or omit it.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": self._image_to_data_uri(image_path)}
                            }
                        ]
                    }
                ],
                temperature=0.1,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                max_tokens=1500,
                n=1,
                stop=None,
                stream=False,
                logprobs=None,
                user="invoice_processor"
            )
        except Exception as e:
            logger.error(f"OpenAI request failed: {e}")
            raise RuntimeError(f"OpenAI API call failed: {e}") from e

        content = response.choices[0].message.content
        try:
            data = json.loads(content)
            return InvoiceData(**data)
        except Exception as e:
            logger.error(f"Failed to parse AI response as JSON: {e}\nContent: {content}")
            raise ValueError("AI response could not be parsed as JSON") from e

# ------------------------------------------------------------------
# 5. Validation logic
# ------------------------------------------------------------------
class InvoiceValidator:
    @staticmethod
    def validate(invoice: InvoiceData) -> Tuple[bool, Optional[str]]:
        errors: List[str] = []

        # Date format checks
        for field in ["invoice_date", "due_date"]:
            try:
                parts = invoice.__dict__[field].split("-")
                if len(parts) != 3:
                    raise ValueError
            except Exception:
                errors.append(f"Invalid {field} format (expected YYYY-MM-DD)")

        # Amount checks
        if invoice.subtotal <= 0:
            errors.append("Subtotal must be positive")
        if invoice.total_amount <= 0:
            errors.append("Total amount must be positive")
        if invoice.tax_amount < 0:
            errors.append("Tax amount cannot be negative")

        # Line items
        for idx, item in enumerate(invoice.line_items, start=1):
            if item.quantity <= 0:
                errors.append(f"Line item {idx} quantity must be positive")
            if item.unit_price <= 0:
                errors.append(f"Line item {idx} unit price must be positive")
            if item.total_amount <= 0:
                errors.append(f"Line item {idx} total amount must be positive")

        return (len(errors) == 0, "\n".join(errors) if errors else None)

# ------------------------------------------------------------------
# 6. End‑to‑end pipeline
# ------------------------------------------------------------------
class InvoiceProcessingPipeline:
    def __init__(self, openai_api_key: str):
        self.openai_api_key = openai_api_key
        self.extractor = None
        self.validator = InvoiceValidator()

    def _get_extractor(self) -> InvoiceExtractor:
        if self.extractor is None:
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY is not set")
            self.extractor = InvoiceExtractor(self.openai_api_key)
        return self.extractor

    def process(self, image_path: str) -> Optional[InvoiceData]:
        """Full pipeline: OCR → AI extraction → validation."""
        logger.info(f"Processing invoice: {image_path}")
        try:
            tesseract_text, easy_text = extract_ocr_text(image_path)
            combined = f"Tesseract OCR:\n{tesseract_text}\n\nEasyOCR:\n{easy_text}"
            extractor = self._get_extractor()
            invoice = extractor.extract(image_path, combined)

            ok, err = self.validator.validate(invoice)
            if not ok:
                logger.warning(f"Validation failed:\n{err}")
                return None
            return invoice
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            return None

# ------------------------------------------------------------------
# 7. FastAPI endpoint
# ------------------------------------------------------------------
app = FastAPI()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---- INSERT YOUR OPENAI KEY HERE --------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY is not set. Set it as an environment variable before running the pipeline.")
# ------------------------------------------------------------------

pipeline = InvoiceProcessingPipeline(OPENAI_API_KEY)

@app.post("/process-invoice/")
async def process_invoice(file: UploadFile = File(...)):
    """Upload an image/PDF and receive structured invoice data."""
    logger.info(f"Received upload: {file.filename}")

    # Validate file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".pdf"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PNG, JPG, JPEG, or PDF.")

    # Save uploaded file
    temp_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{ext}")
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # If PDF, convert first page to image
    if ext == ".pdf":
        try:
            import fitz  # PyMuPDF
            pdf_doc = fitz.open(temp_path)
            page = pdf_doc.load_page(0)
            pix = page.get_pixmap()
            img_path = temp_path.replace(".pdf", ".png")
            pix.save(img_path)
            os.remove(temp_path)
            temp_path = img_path
        except Exception as e:
            os.remove(temp_path)
            logger.error(f"PDF conversion failed: {e}")
            raise HTTPException(status_code=500, detail=f"PDF conversion failed: {e}")

    # Run pipeline
    result = pipeline.process(temp_path)

    # Clean up
    os.remove(temp_path)

    if result:
        return {"status": "success", "data": result.model_dump() if hasattr(result, "model_dump") else result.dict()}
    else:
        import traceback
        # Get the last exception info
        import sys
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_value:
            error_detail = f"Failed to extract invoice data. Error: {str(exc_value)}"
        else:
            error_detail = "Failed to extract invoice data. Check server logs for details."
        raise HTTPException(status_code=400, detail=error_detail)

# ------------------------------------------------------------------
# 8. CLI test harness (optional)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Invoice Processing Pipeline")
    parser.add_argument("file", nargs="?", default=None, help="Path to an image or PDF invoice")
    parser.add_argument("--host", default="0.0.0.0", help="Host for FastAPI server")
    parser.add_argument("--port", type=int, default=8000, help="Port for FastAPI server")
    parser.add_argument("--run-server", action="store_true", help="Start FastAPI server instead of CLI test")

    args = parser.parse_args()

    if args.run_server:
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        # CLI mode – run a single file through the pipeline
        if not args.file:
            logger.error("No file provided. Use --run-server to start the API, or provide a file path.")
            exit(1)
        if not os.path.exists(args.file):
            logger.error(f"File not found: {args.file}")
            exit(1)

        output = pipeline.process(args.file)
        if output:
            print("=== Extracted Invoice Data ===")
            print(json.dumps(output.model_dump(), indent=2))
        else:
            logger.error("Failed to extract data from the provided file.")