"""
OCR Node

Processes images using PaddleOCR to extract text content.
Calculates average confidence and flags low-confidence results.
"""

import logging
from paddleocr import PaddleOCR
from config.settings import settings
from state import AgentState

logger = logging.getLogger(__name__)

# Initialize PaddleOCR once (expensive to load)
_ocr_engine = None


def _get_ocr_engine() -> PaddleOCR:
    """Lazy-initialize the OCR engine (singleton)."""
    global _ocr_engine
    if _ocr_engine is None:
        # Use 'ta' for Tamil OCR support. PaddleOCR handles mixed Tamil+English text.
        ocr_lang = settings.OCR_LANGUAGE
        logger.info(f"Initializing PaddleOCR (lang={ocr_lang})")
        _ocr_engine = PaddleOCR(
            use_angle_cls=True,
            lang=ocr_lang,
        )
    return _ocr_engine


def ocr_process(state: AgentState) -> dict:
    """
    Run OCR on the image at state['image_path'].

    Extracts text lines with confidence scores, concatenates them,
    and calculates the average confidence.

    Returns:
        dict with 'extracted_text' and 'ocr_confidence'.
    """
    image_path = state.get("image_path", "")

    if not image_path:
        logger.warning("OCR node called but no image_path in state")
        return {
            "extracted_text": state.get("telegram_message", ""),
            "ocr_confidence": 1.0,
        }

    logger.info(f"Running OCR on: {image_path}")

    try:
        ocr = _get_ocr_engine()
        result = ocr.ocr(image_path)

        if not result or not result[0]:
            logger.warning("OCR returned no results")
            return {
                "extracted_text": "",
                "ocr_confidence": 0.0,
                "error": "OCR could not detect any text in the image.",
            }

        # Extract text lines and confidence scores
        lines = []
        confidences = []

        for line_info in result[0]:
            text = line_info[1][0]       # Detected text
            confidence = line_info[1][1]  # Confidence score
            lines.append(text)
            confidences.append(confidence)
            logger.debug(f"  OCR line: '{text}' (confidence: {confidence:.3f})")

        extracted_text = "\n".join(lines)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        logger.info(
            f"OCR extracted {len(lines)} lines, "
            f"avg confidence: {avg_confidence:.3f}"
        )

        # Warn if confidence is low
        if avg_confidence < settings.OCR_CONFIDENCE_THRESHOLD:
            logger.warning(
                f"Low OCR confidence ({avg_confidence:.2f} < "
                f"{settings.OCR_CONFIDENCE_THRESHOLD})"
            )

        return {
            "extracted_text": extracted_text,
            "ocr_confidence": avg_confidence,
        }

    except Exception as e:
        logger.error(f"OCR processing failed: {e}", exc_info=True)
        return {
            "extracted_text": "",
            "ocr_confidence": 0.0,
            "error": f"OCR processing failed: {str(e)}",
        }
