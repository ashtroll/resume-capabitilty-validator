"""
PDF Parser Service — extracts raw text AND embedded hyperlinks from resume PDFs.

Strategy:
  1. Primary: pdfplumber (best for structured/tabular resumes)
  2. Fallback: PyMuPDF/fitz (handles more edge cases)
  3. Last resort: pytesseract OCR (for image-based/scanned PDFs)
  4. Always: extract embedded hyperlinks via PyMuPDF
"""

import logging
from pathlib import Path

import pdfplumber
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFParser:
    """Extracts text content and embedded hyperlinks from PDF resume files."""

    @staticmethod
    def parse(file_path: str | Path) -> str:
        """
        Extract text from a PDF file using a cascading strategy.
        Also extracts embedded hyperlinks and appends them to the text
        so the entity extractor can find them.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Extracted text content (with appended hyperlinks) as a string.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If no text could be extracted.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        # Strategy 1: pdfplumber (best for most resumes)
        text = PDFParser._parse_with_pdfplumber(file_path)

        # Strategy 2: PyMuPDF fallback (handles edge cases)
        if not text or len(text.strip()) < 50:
            logger.info("pdfplumber yielded insufficient text, falling back to PyMuPDF")
            text = PDFParser._parse_with_pymupdf(file_path)

        # Strategy 3: OCR fallback (for scanned/image PDFs)
        if not text or len(text.strip()) < 50:
            logger.info("PyMuPDF yielded insufficient text, attempting OCR")
            text = PDFParser._parse_with_ocr(file_path)

        if not text or len(text.strip()) < 20:
            raise ValueError(
                f"Could not extract meaningful text from {file_path.name}. "
                "The PDF may be empty, corrupted, or entirely image-based without OCR support."
            )

        # Always extract embedded hyperlinks and append them
        hyperlinks = PDFParser.extract_hyperlinks(file_path)
        if hyperlinks:
            link_block = "\n\nExtracted Hyperlinks:\n" + "\n".join(hyperlinks)
            text = text.strip() + link_block
            logger.info(f"Extracted {len(hyperlinks)} embedded hyperlinks from PDF")

        return text.strip()

    @staticmethod
    def extract_hyperlinks(file_path: str | Path) -> list[str]:
        """
        Extract embedded hyperlink URIs from the PDF using PyMuPDF.

        Many resumes use clickable icons (GitHub, LinkedIn, etc.) that
        don't show the URL in the visible text. This method captures those.

        Args:
            file_path: Path to the PDF file.

        Returns:
            List of unique URI strings found in the PDF.
        """
        file_path = Path(file_path)
        urls: list[str] = []
        seen: set[str] = set()

        try:
            with fitz.open(file_path) as doc:
                for page in doc:
                    for link in page.get_links():
                        uri = link.get("uri", "")
                        if uri and uri not in seen:
                            seen.add(uri)
                            urls.append(uri)
                            logger.debug(f"Found embedded link: {uri}")
        except Exception as e:
            logger.warning(f"Hyperlink extraction failed: {e}")

        return urls

    @staticmethod
    def _parse_with_pdfplumber(file_path: Path) -> str:
        """Extract text using pdfplumber — great for structured layouts."""
        try:
            pages_text = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append(page_text)
            return "\n\n".join(pages_text)
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}")
            return ""

    @staticmethod
    def _parse_with_pymupdf(file_path: Path) -> str:
        """Extract text using PyMuPDF — handles more PDF variants."""
        try:
            pages_text = []
            with fitz.open(file_path) as doc:
                for page in doc:
                    page_text = page.get_text("text")
                    if page_text:
                        pages_text.append(page_text)
            return "\n\n".join(pages_text)
        except Exception as e:
            logger.warning(f"PyMuPDF failed: {e}")
            return ""

    @staticmethod
    def _parse_with_ocr(file_path: Path) -> str:
        """
        Extract text via OCR — last resort for scanned PDFs.
        Requires tesseract to be installed on the system.
        """
        try:
            import pytesseract
            from PIL import Image
            import io

            pages_text = []
            with fitz.open(file_path) as doc:
                for page_num, page in enumerate(doc):
                    # Render page to image at 300 DPI for good OCR quality
                    pix = page.get_pixmap(dpi=300)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    page_text = pytesseract.image_to_string(img)
                    if page_text:
                        pages_text.append(page_text)

            return "\n\n".join(pages_text)
        except ImportError:
            logger.warning("pytesseract or Pillow not installed — OCR unavailable")
            return ""
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return ""

