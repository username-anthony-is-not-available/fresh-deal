"""
Flyer Upload and OCR Service

This service allows users to upload PDF or image files of grocery flyers
and uses LLM vision capabilities to extract structured deal data.

Based on Reddit thread feedback:
- Users want to upload PDFs/images and get structured text output
- GPT-4 Vision / Claude can read flyer images effectively
- The output should be in a format suitable for meal planning
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional, List
import base64
import io
import logging
import json
import re
from pydantic import BaseModel
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/flyer", tags=["flyer-upload"])


class ExtractedDeal(BaseModel):
    """Schema for an extracted deal from a flyer."""

    product_name: str
    price: float
    original_price: Optional[float] = None
    quantity: Optional[str] = None
    unit: str = "each"
    store: Optional[str] = None
    discount_pct: Optional[float] = None
    notes: Optional[str] = None


class FlyerExtractionResult(BaseModel):
    """Result of flyer extraction."""

    success: bool
    store_detected: Optional[str] = None
    deal_count: int
    deals: List[ExtractedDeal]
    raw_text: Optional[str] = None
    errors: List[str] = []


# Supported file types
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# The extraction prompt - optimized based on Reddit thread feedback
# Users reported that marketing text (e.g., "Watatow offre du siècle") causes noise
EXTRACTION_PROMPT = """You are analyzing a grocery store flyer image. Extract ALL product deals visible in this image.

For each product, extract:
1. Product name (just the product, ignore marketing slogans)
2. Sale price (the current discounted price)
3. Original/regular price (if shown)
4. Quantity (e.g., "2 for", "1 kg", "500g")
5. Unit type (each, kg, lb, L, 100g)
6. Any loyalty points mentioned (e.g., "2000 PC Optimum points")

IMPORTANT RULES:
- IGNORE marketing text like "Offre du siècle", "Watatow", "Super rabais"
- IGNORE store logos and branding
- Focus ONLY on actual products with prices
- If price shows "2/5$" or "2 pour 5$", calculate per-unit price
- French product names are acceptable

Output as JSON array:
```json
[
  {
    "product_name": "Chicken breast",
    "price": 4.99,
    "original_price": 8.99,
    "quantity": "per kg",
    "unit": "kg",
    "discount_pct": 44,
    "notes": "2000 PC Optimum points"
  }
]
```

If you can identify the store name, include it at the start of your response like:
STORE: Metro
```json
...
```"""


class FlyerOCRService:
    """
    Service for extracting deal data from flyer images using LLM vision.
    """

    def __init__(self):
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            logger.warning("OPENROUTER_API_KEY not set. OCR service will not work.")
            self.client = None
        else:
            self.client = OpenAI(base_url=settings.OPENROUTER_BASE_URL, api_key=api_key)
        # Use a vision-capable model
        self.vision_model = "anthropic/claude-3.5-sonnet"  # Claude has good vision

    async def extract_deals_from_image(
        self, image_data: bytes, content_type: str, store_hint: Optional[str] = None
    ) -> FlyerExtractionResult:
        """
        Extract deals from an image using LLM vision.

        Args:
            image_data: Raw image bytes
            content_type: MIME type of the image
            store_hint: Optional hint about which store the flyer is from
        """
        if not self.client:
            return FlyerExtractionResult(
                success=False,
                deal_count=0,
                deals=[],
                errors=["LLM API not configured. Set OPENROUTER_API_KEY."],
            )

        try:
            # Encode image as base64
            image_b64 = base64.b64encode(image_data).decode("utf-8")

            # Build the prompt
            prompt = EXTRACTION_PROMPT
            if store_hint:
                prompt += (
                    f"\n\nNote: The user indicated this flyer is from {store_hint}."
                )

            # Call the vision model
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{content_type};base64,{image_b64}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=4096,
            )

            # Parse the response
            result_text = response.choices[0].message.content or ""
            return self._parse_extraction_result(result_text, store_hint)

        except Exception as e:
            logger.error(f"Error extracting deals from image: {e}")
            return FlyerExtractionResult(
                success=False, deal_count=0, deals=[], errors=[str(e)]
            )

    def _parse_extraction_result(
        self, result_text: str, store_hint: Optional[str]
    ) -> FlyerExtractionResult:
        """Parse the LLM response into structured deals."""
        deals = []
        errors = []
        store_detected = store_hint

        try:
            # Check for store detection
            store_match = re.search(r"STORE:\s*(\w+)", result_text, re.IGNORECASE)
            if store_match:
                store_detected = store_match.group(1)

            # Extract JSON from response
            json_match = re.search(r"\[[\s\S]*\]", result_text)
            if json_match:
                json_str = json_match.group(0)
                raw_deals = json.loads(json_str)

                for raw_deal in raw_deals:
                    try:
                        deal = ExtractedDeal(
                            product_name=raw_deal.get("product_name", "Unknown"),
                            price=float(raw_deal.get("price", 0)),
                            original_price=float(raw_deal["original_price"])
                            if raw_deal.get("original_price")
                            else None,
                            quantity=raw_deal.get("quantity"),
                            unit=raw_deal.get("unit", "each"),
                            store=store_detected,
                            discount_pct=float(raw_deal["discount_pct"])
                            if raw_deal.get("discount_pct")
                            else None,
                            notes=raw_deal.get("notes"),
                        )
                        deals.append(deal)
                    except Exception as e:
                        errors.append(f"Failed to parse deal: {e}")
            else:
                errors.append("No JSON array found in LLM response")

        except json.JSONDecodeError as e:
            errors.append(f"JSON parsing error: {e}")
        except Exception as e:
            errors.append(f"Unexpected error: {e}")

        return FlyerExtractionResult(
            success=len(deals) > 0,
            store_detected=store_detected,
            deal_count=len(deals),
            deals=deals,
            raw_text=result_text if not deals else None,
            errors=errors,
        )


# Singleton service instance
ocr_service = FlyerOCRService()


@router.post("/upload", response_model=FlyerExtractionResult)
async def upload_flyer(
    file: UploadFile = File(..., description="Flyer image (JPG, PNG, PDF)"),
    store: Optional[str] = Form(None, description="Store name hint (e.g., Metro, IGA)"),
):
    """
    Upload a grocery flyer image and extract deals using AI vision.

    This endpoint accepts flyer images (JPG, PNG, WebP) or PDFs and uses
    AI vision capabilities to extract structured deal information.

    **Supported formats:** JPG, PNG, GIF, WebP, PDF (first page only)
    **Max file size:** 20MB

    The extracted data includes:
    - Product names (cleaned of marketing text)
    - Prices (sale and original)
    - Quantities and units
    - Discount percentages
    - Loyalty point offers

    Based on Reddit r/QuebecTI feedback, this endpoint filters out
    marketing noise like "Watatow offre du siècle" to provide clean data.
    """
    # Validate file extension
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    # Determine content type
    content_type = file.content_type or "image/jpeg"

    # Handle PDF - convert first page to image
    if ext == ".pdf":
        try:
            content, content_type = await convert_pdf_to_image(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to process PDF: {e}")

    # Extract deals
    result = await ocr_service.extract_deals_from_image(content, content_type, store)

    return result


@router.post("/upload/batch")
async def upload_multiple_flyers(
    files: List[UploadFile] = File(..., description="Multiple flyer images"),
    store: Optional[str] = Form(None, description="Store name hint"),
):
    """
    Upload multiple flyer pages and extract deals from all of them.

    This is useful for multi-page flyers where you want to process
    all pages at once.
    """
    all_deals = []
    all_errors = []
    store_detected = store

    for file in files:
        try:
            content = await file.read()
            content_type = file.content_type or "image/jpeg"

            result = await ocr_service.extract_deals_from_image(
                content, content_type, store_detected
            )

            if result.store_detected and not store_detected:
                store_detected = result.store_detected

            all_deals.extend(result.deals)
            all_errors.extend(result.errors)

        except Exception as e:
            all_errors.append(f"Error processing {file.filename}: {e}")

    # Deduplicate deals by product name + price
    seen = set()
    unique_deals = []
    for deal in all_deals:
        key = f"{deal.product_name}|{deal.price}"
        if key not in seen:
            seen.add(key)
            unique_deals.append(deal)

    return FlyerExtractionResult(
        success=len(unique_deals) > 0,
        store_detected=store_detected,
        deal_count=len(unique_deals),
        deals=unique_deals,
        errors=all_errors if all_errors else [],
    )


@router.get("/formats")
async def get_supported_formats():
    """
    Get information about supported file formats and usage tips.
    """
    return {
        "supported_formats": list(ALLOWED_EXTENSIONS),
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
        "tips": [
            "For best results, use clear, high-resolution images",
            "Crop out non-deal content (store logos, decorative elements)",
            "Upload one page at a time for multi-page flyers",
            "Specify the store name if known for better accuracy",
            "PDF files will have their first page extracted",
        ],
        "example_stores": ["Metro", "IGA", "Maxi", "Provigo", "Super C", "Walmart"],
    }


async def convert_pdf_to_image(pdf_bytes: bytes) -> tuple:
    """
    Convert PDF first page to image for processing.

    Note: This requires pdf2image and poppler to be installed.
    Falls back to returning an error if not available.
    """
    try:
        from pdf2image import convert_from_bytes

        # Convert first page only
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1)

        if not images:
            raise ValueError("No pages found in PDF")

        # Convert PIL image to bytes
        img_buffer = io.BytesIO()
        images[0].save(img_buffer, format="PNG")
        img_buffer.seek(0)

        return img_buffer.read(), "image/png"

    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="PDF processing not available. Please upload an image instead (JPG, PNG).",
        )
