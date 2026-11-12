import io
from typing import List, Tuple, Optional
from pypdf import PdfReader


class ParsedPage:
    """Represents text extracted from a specific page of a document."""
    def __init__(self, text: str, page_number: int):
        self.text = text
        self.page_number = page_number


class TextChunk:
    """A granular chunk of text ready for vector embedding and citation tracking."""
    def __init__(self, content: str, chunk_index: int, page: Optional[int] = None):
        self.content = content
        self.chunk_index = chunk_index
        self.page = page

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "chunk_index": self.chunk_index,
            "page": self.page,
        }


class DocumentParser:
    """
    Handles file text extraction (PDF, TXT, MD) and semantic overlapping chunking.
    """

    @classmethod
    def extract_text(cls, file_bytes: bytes, filename: str) -> List[ParsedPage]:
        """
        Extracts text from file bytes based on file extension.
        Returns a list of ParsedPage objects preserving page numbers.
        """
        lower_name = filename.lower()

        if lower_name.endswith(".pdf"):
            return cls._extract_pdf(file_bytes)
        elif lower_name.endswith((".txt", ".md", ".markdown")):
            return cls._extract_plain_text(file_bytes)
        else:
            raise ValueError(f"Unsupported file format: {filename}. Supported: PDF, TXT, MD.")

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> List[ParsedPage]:
        pages = []
        reader = PdfReader(io.BytesIO(file_bytes))
        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            cleaned = page_text.strip()
            if cleaned:
                pages.append(ParsedPage(text=cleaned, page_number=idx + 1))
        return pages

    @staticmethod
    def _extract_plain_text(file_bytes: bytes) -> List[ParsedPage]:
        text = file_bytes.decode("utf-8", errors="replace").strip()
        if not text:
            return []
        # TXT/MD files are treated as single-page documents
        return [ParsedPage(text=text, page_number=1)]

    @classmethod
    def chunk_document(
        cls,
        pages: List[ParsedPage],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> List[TextChunk]:
        """
        Splits extracted pages into overlapping chunks while preserving sentence boundaries
        and exact page number attribution.
        """
        all_chunks: List[TextChunk] = []
        current_chunk_index = 0

        for page in pages:
            page_text = page.text
            if not page_text:
                continue

            # Split into chunks using recursive separator priority
            chunks_for_page = cls._recursive_split(
                text=page_text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )

            for chunk_content in chunks_for_page:
                if chunk_content.strip():
                    all_chunks.append(
                        TextChunk(
                            content=chunk_content.strip(),
                            chunk_index=current_chunk_index,
                            page=page.page_number,
                        )
                    )
                    current_chunk_index += 1

        return all_chunks

    @classmethod
    def _recursive_split(
        cls,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
        separators: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Recursively splits text on natural boundaries (\n\n, \n, ' ') to preserve semantics.
        """
        if len(text) <= chunk_size:
            return [text]

        if separators is None:
            separators = ["\n\n", "\n", ". ", " ", ""]

        chosen_separator = ""
        for sep in separators:
            if sep in text:
                chosen_separator = sep
                break

        if chosen_separator:
            parts = text.split(chosen_separator)
        else:
            parts = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]
            return parts

        chunks = []
        current_chunk = ""

        for part in parts:
            candidate = f"{current_chunk}{chosen_separator}{part}" if current_chunk else part
            if len(candidate) <= chunk_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    # Compute overlap from end of current chunk
                    if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                        current_chunk = current_chunk[-chunk_overlap:] + chosen_separator + part
                    else:
                        current_chunk = part
                else:
                    chunks.append(part[:chunk_size])
                    current_chunk = part[chunk_size - chunk_overlap:]

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
