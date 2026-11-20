"""Bounded text extraction for user-reviewed Gria context; never scores a file."""
import io
import zipfile
from pathlib import Path

import pdfplumber
from core.auth import get_current_user
from docx import Document
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

router = APIRouter(prefix='/documents', tags=['Document context'])
MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 4000
MAX_PAGES = 30
MAX_UNCOMPRESSED = 20 * 1024 * 1024


@router.post('/extract')
async def extract_document(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    filename = Path(file.filename or '').name
    ext = Path(filename).suffix.lower()
    if ext not in ('.txt', '.pdf', '.docx'):
        raise HTTPException(status_code=400, detail='Only TXT, text-based PDF, and DOCX files are supported. Images cannot be used as NDVI measurements.')
    raw = await file.read(MAX_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=400, detail='The file is empty.')
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail='The file exceeds 5 MB.')
    try:
        if ext == '.txt':
            text = raw.decode('utf-8-sig')
        elif ext == '.pdf':
            if not raw.startswith(b'%PDF-'):
                raise ValueError('Invalid PDF signature')
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                if len(pdf.pages) > MAX_PAGES:
                    raise ValueError('PDF has more than 30 pages')
                parts, length = [], 0
                for page in pdf.pages:
                    part = page.extract_text() or ''
                    parts.append(part)
                    length += len(part)
                    if length > MAX_TEXT:
                        break
                text = '\n'.join(parts)
        else:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                if len(entries) > 1000 or sum(item.file_size for item in entries) > MAX_UNCOMPRESSED:
                    raise ValueError('DOCX content exceeds the extraction limit')
                if any(item.file_size > MAX_UNCOMPRESSED or (item.compress_size and item.file_size / item.compress_size > 200) for item in entries):
                    raise ValueError('DOCX compression ratio exceeds the extraction limit')
                if not {'[Content_Types].xml', 'word/document.xml'}.issubset(set(archive.namelist())):
                    raise ValueError('Invalid DOCX file')
            doc = Document(io.BytesIO(raw))
            # Bound the join: a 20 MB DOCX can hold millions of characters, and the
            # PDF branch already stops at MAX_TEXT. Collect only what is used.
            paragraphs, length = [], 0
            for paragraph in doc.paragraphs:
                paragraphs.append(paragraph.text)
                length += len(paragraph.text) + 1
                if length > MAX_TEXT:
                    break
            text = '\n'.join(paragraphs)
    except (ValueError, UnicodeDecodeError, zipfile.BadZipFile, OSError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f'Could not extract text: {exc}') from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail='The document could not be read. It may be malformed or encrypted.') from exc
    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail='No text was found. Scanned PDFs and images require OCR, which is not available.')
    return {'file_name': filename, 'text': text[:MAX_TEXT], 'truncated': len(text) > MAX_TEXT,
            'notice': 'Review the extracted text before sharing it with Gria. It is context only and does not generate model inputs.'}
