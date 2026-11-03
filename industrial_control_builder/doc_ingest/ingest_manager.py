"""
Multi-Modal Document & Context Ingestion Engine
Extracts pinouts, operating parameters, and sequence guides from:
PDF, Excel (.xlsx/.csv), Word (.docx), JSON, TXT, and Images.
"""

import os
import json
import csv
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional

class DocumentIngestManager:
    """Ingests multi-format documents and synthesizes structured technical context."""

    @staticmethod
    def ingest_file(file_path: str) -> Dict[str, Any]:
        """Ingests a file and extracts structured text, tables, and metadata."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        _, ext = os.path.splitext(file_path.lower())

        if ext == ".txt":
            return DocumentIngestManager._parse_txt(file_path)
        elif ext == ".json":
            return DocumentIngestManager._parse_json(file_path)
        elif ext == ".csv":
            return DocumentIngestManager._parse_csv(file_path)
        elif ext in (".xlsx", ".xlsm"):
            return DocumentIngestManager._parse_xlsx(file_path)
        elif ext == ".docx":
            return DocumentIngestManager._parse_docx(file_path)
        elif ext == ".pdf":
            return DocumentIngestManager._parse_pdf(file_path)
        elif ext in (".png", ".jpg", ".jpeg", ".bmp"):
            return DocumentIngestManager._parse_image(file_path)
        else:
            # Fallback raw text attempt
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(5000)
                return {"type": "raw_text", "filename": os.path.basename(file_path), "content": content}
            except Exception as e:
                return {"type": "unsupported", "filename": os.path.basename(file_path), "error": str(e)}

    @staticmethod
    def _parse_txt(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return {
            "type": "text",
            "filename": os.path.basename(path),
            "text": text,
            "char_count": len(text)
        }

    @staticmethod
    def _parse_json(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        return {
            "type": "json",
            "filename": os.path.basename(path),
            "data": data
        }

    @staticmethod
    def _parse_csv(path: str) -> Dict[str, Any]:
        header, samples, row_count = [], [], 0
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            for row in reader:
                if not row:
                    continue
                row_count += 1
                if len(samples) < 9:
                    samples.append(row)
        return {
            "type": "table_csv",
            "filename": os.path.basename(path),
            "header": header,
            "row_count": row_count,
            "sample_rows": [header] + samples if header else samples
        }

    @staticmethod
    def _parse_docx(path: str) -> Dict[str, Any]:
        """Extracts text paragraphs from a Word .docx package using internal XML parsing."""
        paragraphs = []
        try:
            with zipfile.ZipFile(path) as z:
                xml_content = z.read("word/document.xml")
                root = ET.fromstring(xml_content)
                # XML namespace for word
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                for p in root.findall('.//w:p', ns):
                    texts = [node.text for node in p.findall('.//w:t', ns) if node.text]
                    if texts:
                        paragraphs.append("".join(texts))
        except Exception as e:
            paragraphs.append(f"Error parsing .docx XML: {e}")

        return {
            "type": "word_document",
            "filename": os.path.basename(path),
            "paragraphs": paragraphs,
            "full_text": "\n".join(paragraphs)
        }

    @staticmethod
    def _parse_xlsx(path: str) -> Dict[str, Any]:
        """Extracts sheets and cell values from an Excel .xlsx using ZIP and sharedStrings XML."""
        try:
            from openpyxl import load_workbook
            book = load_workbook(path, read_only=True, data_only=True)
            sheets = []
            for sheet in book.worksheets:
                iterator = sheet.iter_rows(values_only=True)
                header = [str(v) if v is not None else "" for v in next(iterator, ())]
                sample = []
                for row in iterator:
                    if any(v is not None for v in row):
                        sample.append(list(row))
                    if len(sample) >= 8:
                        break
                sheets.append({"name": sheet.title, "header": header, "sample_rows": sample})
            book.close()
            first = sheets[0] if sheets else {"header": [], "sample_rows": []}
            return {"type": "excel_spreadsheet", "filename": os.path.basename(path),
                    "sheet_names": [s["name"] for s in sheets], "sheets": sheets,
                    "header": first["header"], "sample_rows": first["sample_rows"]}
        except ImportError:
            pass
        sheet_data = []
        try:
            with zipfile.ZipFile(path) as z:
                # Read shared strings if present
                shared_strings = []
                if "xl/sharedStrings.xml" in z.namelist():
                    ss_xml = z.read("xl/sharedStrings.xml")
                    ss_root = ET.fromstring(ss_xml)
                    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    for si in ss_root.findall('.//s:si', ns):
                        t_nodes = si.findall('.//s:t', ns)
                        shared_strings.append("".join([t.text or "" for t in t_nodes]))

                # Read Sheet 1
                if "xl/worksheets/sheet1.xml" in z.namelist():
                    sheet_xml = z.read("xl/worksheets/sheet1.xml")
                    root = ET.fromstring(sheet_xml)
                    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    for row in root.findall('.//s:row', ns):
                        row_vals = []
                        for c in row.findall('.//s:c', ns):
                            v_node = c.find('s:v', ns)
                            t_attr = c.get('t')
                            val = v_node.text if v_node is not None else ""
                            if t_attr == 's' and val.isdigit() and int(val) < len(shared_strings):
                                val = shared_strings[int(val)]
                            row_vals.append(val)
                        if row_vals:
                            sheet_data.append(row_vals)
        except Exception as e:
            sheet_data.append([f"Error parsing Excel XML: {e}"])

        return {
            "type": "excel_spreadsheet",
            "filename": os.path.basename(path),
            "header": sheet_data[0] if sheet_data else [],
            "sample_rows": sheet_data[:10],
            "total_rows": len(sheet_data)
        }

    @staticmethod
    def _parse_pdf(path: str) -> Dict[str, Any]:
        """Extracts text content and pinout mentions from PDF."""
        extracted_text = ""
        warning = ""
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            for page in reader.pages[:15]:  # limit pages to keep memory clean
                t = page.extract_text()
                if t:
                    extracted_text += t + "\n"
        except ImportError:
            warning = "Install pypdf to extract PDF text."
        except Exception as e:
            warning = f"PDF text extraction failed: {e}"
        if not extracted_text and not warning:
            warning = "No selectable text found; scanned pages need OCR, which is not currently available."

        return {
            "type": "pdf_manual",
            "filename": os.path.basename(path),
            "text_snippet": extracted_text[:4000],
            "estimated_length": len(extracted_text),
            "warning": warning
        }

    @staticmethod
    def _parse_image(path: str) -> Dict[str, Any]:
        """Provides metadata and technical summary for images / diagrams."""
        size = os.path.getsize(path) if os.path.exists(path) else 0
        return {
            "type": "schematic_image",
            "filename": os.path.basename(path),
            "file_size_bytes": size,
            "note": "Image registered as a reference only; image OCR/vision extraction is not implemented."
        }

    @staticmethod
    def build_summary_for_llm(doc_results: List[Dict[str, Any]]) -> str:
        """Compresses ingested documents into a high-density, low-token prompt context."""
        summary_lines = ["--- INGESTED SYSTEM SPECIFICATIONS & DOCUMENTS ---"]
        for doc in doc_results:
            fname = doc.get("filename", "unknown")
            dtype = doc.get("type", "unknown")
            if dtype == "table_csv":
                summary_lines.append(f"[File: {fname} (CSV Table)] Columns: {doc.get('header')}")
                for row in doc.get("sample_rows", [])[:4]:
                    summary_lines.append(f"  Row: {row}")
            elif dtype == "excel_spreadsheet":
                summary_lines.append(f"[File: {fname} (Excel workbook)] Sheets: {doc.get('sheet_names', ['Sheet1'])}; First-sheet columns: {doc.get('header')}")
                for row in doc.get("sample_rows", [])[:4]:
                    summary_lines.append(f"  Row: {row}")
            elif dtype == "word_document":
                summary_lines.append(f"[File: {fname} (Word Manual)] Excerpt:")
                for p in doc.get("paragraphs", [])[:5]:
                    summary_lines.append(f"  - {p}")
            elif dtype == "pdf_manual":
                summary_lines.append(f"[File: {fname} (PDF Guide)] Excerpt: {doc.get('text_snippet', '')[:300]}...")
                if doc.get("warning"):
                    summary_lines.append(f"  Extraction note: {doc['warning']}")
            elif dtype == "schematic_image":
                summary_lines.append(f"[File: {fname} (image reference)] {doc.get('note', '')}")
            elif dtype in ("text", "json"):
                text = str(doc.get("text") or doc.get("data"))[:400]
                summary_lines.append(f"[File: {fname}] Content: {text}...")
        summary_lines.append("-------------------------------------------------")
        return "\n".join(summary_lines)
