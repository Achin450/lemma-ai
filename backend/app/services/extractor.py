import io
from pathlib import Path
from pypdf import PdfReader
from docx import Document
from app.config import settings

class ExtractionError(Exception):
    """Base exception for document extraction errors."""
    pass

class UnsupportedFileTypeError(ExtractionError):
    """Raised when file extension is not supported."""
    pass

class FileSizeExceededError(ExtractionError):
    """Raised when file size exceeds the allowed limit."""
    pass

class DocumentExtractorService:
    @staticmethod
    def validate_file(filename: str, file_size_bytes: int) -> None:
        """Validates the file extension and size constraints."""
        # Validate size
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size_bytes > max_bytes:
            raise FileSizeExceededError(
                f"File size exceeds the maximum limit of {settings.MAX_FILE_SIZE_MB}MB."
            )

        # Validate extension
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"File type '.{ext}' is not supported. Allowed formats: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

    @classmethod
    def extract_text(cls, filename: str, content: bytes) -> str:
        """
        Extracts raw text from document content bytes based on file extension.
        Supports: PDF, DOCX, and TXT.
        """
        cls.validate_file(filename, len(content))
        ext = Path(filename).suffix.lower().lstrip(".")

        try:
            if ext == "txt":
                return cls._extract_txt(content)
            elif ext == "docx":
                return cls._extract_docx(content)
            elif ext == "pdf":
                return cls._extract_pdf(content)
            else:
                raise UnsupportedFileTypeError(f"Unsupported file extension: {ext}")
        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Failed to extract text from {filename}: {str(e)}") from e

    @staticmethod
    def _extract_txt(content: bytes) -> str:
        """Extracts text from a raw TXT byte content, attempting UTF-8 then Latin-1."""
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return content.decode("latin-1")
            except UnicodeDecodeError as e:
                raise ExtractionError("Failed to decode TXT file with UTF-8 or Latin-1 encoding.") from e

    @staticmethod
    def _extract_docx(content: bytes) -> str:
        """Extracts text from DOCX bytes using python-docx, preserving order."""
        try:
            doc_file = io.BytesIO(content)
            doc = Document(doc_file)
            
            paragraphs = []
            # In python-docx, iterating blocks preserving order can be tricky without internal API.
            # Using iter_inner_content or just a simple block traversal if needed.
            # A common approach without deep internals is to extract text from all blocks.
            # For simplicity, we just extract paragraph text, and handle tables if needed, 
            # but ideally keeping order.
            
            # Since python-docx doesn't easily expose an ordered iterator of paras and tables together,
            # we will iterate through the document's body elements.
            from docx.document import Document as _Document
            from docx.oxml.text.paragraph import CT_P
            from docx.oxml.table import CT_Tbl
            from docx.table import _Cell, Table
            from docx.text.paragraph import Paragraph

            for child in doc.element.body:
                if isinstance(child, CT_P):
                    p = Paragraph(child, doc)
                    if p.text.strip():
                        paragraphs.append(p.text)
                elif isinstance(child, CT_Tbl):
                    table = Table(child, doc)
                    for row in table.rows:
                        for cell in row.cells:
                            for p in cell.paragraphs:
                                if p.text.strip():
                                    paragraphs.append(p.text)

            return "\n".join(paragraphs)
        except Exception as e:
            raise ExtractionError(f"Corrupted or invalid DOCX document: {str(e)}") from e

    @staticmethod
    def _extract_pdf(content: bytes) -> str:
        """Extracts text from PDF bytes using pypdf. Falls back to OCR if empty."""
        try:
            pdf_file = io.BytesIO(content)
            reader = PdfReader(pdf_file)
            
            if reader.is_encrypted:
                try:
                    # Try decrypting with empty password
                    reader.decrypt("")
                except Exception as e:
                    raise ExtractionError("Encrypted or password-protected PDF files are not supported.") from e
            
            text_pages = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_pages.append(page_text)
                    
            if not text_pages:
                # Fallback to OCR using pdf2image and pytesseract
                try:
                    import pytesseract
                    from pdf2image import convert_from_bytes
                    images = convert_from_bytes(content)
                    for img in images:
                        text = pytesseract.image_to_string(img)
                        if text.strip():
                            text_pages.append(text)
                except Exception as e:
                    raise ExtractionError("No extractable text found in PDF, and OCR fallback failed. Note: OCR requires Tesseract and Poppler installed on the system.") from e
                
                if not text_pages:
                    raise ExtractionError("No extractable text found in PDF even after OCR fallback.")
                
            return "\n\n".join(text_pages)
        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Invalid PDF document: {str(e)}") from e
