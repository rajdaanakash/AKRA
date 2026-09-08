import os
import re
import json
import tempfile
import requests
from datetime import datetime
from markitdown import MarkItDown

# Custom session with realistic User-Agent to avoid 403 Forbidden errors
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 AKRA/2.0"
})

# Global MarkItDown instance
try:
    _markitdown = MarkItDown(requests_session=_session, enable_builtins=True)
except Exception as e:
    print(f"Warning initializing MarkItDown: {e}")
    _markitdown = MarkItDown(enable_builtins=True)

YOUTUBE_REGEX = re.compile(
    r'(https?://)?(www\.|m\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
    re.IGNORECASE
)

def extract_youtube_urls(text: str):
    """Finds all YouTube URLs in a text string."""
    if not text:
        return []
    matches = YOUTUBE_REGEX.findall(text)
    urls = []
    for match in matches:
        # Full matched pattern reconstruction
        vid_id = match[3]
        urls.append(f"https://www.youtube.com/watch?v={vid_id}")
    return list(dict.fromkeys(urls)) # Remove duplicates while preserving order

def convert_source_to_markdown(source, filename=None, ext=None):
    """
    Universal converter using Microsoft MarkItDown.
    Supports:
      - YouTube URLs (extracts video metadata and transcripts/captions)
      - Web URLs / Wikipedia / HTML
      - Documents: PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx, .csv)
      - Audio: .mp3, .wav, .m4a (speech transcription into Markdown)
      - Images: .png, .jpg, .jpeg, .webp (EXIF & OCR/captions)
      - Text/Code files: .txt, .json, .py, .md, etc.
    """
    try:
        # 1. YouTube URL Conversion
        if isinstance(source, str) and YOUTUBE_REGEX.search(source):
            clean_url = source.strip()
            res = _markitdown.convert(clean_url)
            title = res.title or "YouTube Video Transcript"
            md_text = res.markdown or str(res)
            return {
                "status": "success",
                "type": "youtube",
                "title": title,
                "markdown": md_text,
                "source": clean_url
            }

        # 2. General Web URL Conversion
        if isinstance(source, str) and (source.startswith("http://") or source.startswith("https://")):
            clean_url = source.strip()
            res = _markitdown.convert(clean_url)
            title = res.title or "Web Page"
            md_text = res.markdown or str(res)
            return {
                "status": "success",
                "type": "web",
                "title": title,
                "markdown": md_text,
                "source": clean_url
            }

        # 3. File Path Conversion
        if isinstance(source, str) and os.path.isfile(source):
            file_path = source
            base_fn = filename or os.path.basename(file_path)
            res = _markitdown.convert(file_path)
            title = res.title or base_fn
            md_text = res.markdown or str(res)
            
            # Determine high-level category
            lower_fn = base_fn.lower()
            if any(lower_fn.endswith(e) for e in ['.mp3', '.wav', '.m4a', '.ogg', '.flac']):
                file_type = "audio"
            elif any(lower_fn.endswith(e) for e in ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif']):
                file_type = "image"
            elif any(lower_fn.endswith(e) for e in ['.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv']):
                file_type = "document"
            else:
                file_type = "file"

            return {
                "status": "success",
                "type": file_type,
                "title": title,
                "markdown": md_text,
                "source": base_fn
            }

        # 4. Raw Bytes / In-memory File
        if isinstance(source, bytes):
            suffix = ext if (ext and ext.startswith('.')) else (f".{ext}" if ext else ".tmp")
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
                tf.write(source)
                temp_path = tf.name

            try:
                res = _markitdown.convert(temp_path)
                title = res.title or (filename or "Attached File")
                md_text = res.markdown or str(res)
                return {
                    "status": "success",
                    "type": "document",
                    "title": title,
                    "markdown": md_text,
                    "source": filename or "Attachment"
                }
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass

        return {
            "status": "error",
            "message": "Unsupported source type for MarkItDown conversion."
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"MarkItDown conversion error: {str(e)}"
        }

def save_sector_document(history_dir, username, sector_name, filename, markdown_content, doc_type="document"):
    """
    Saves converted Markdown document into the user's private sector archive
    and indexes it in sector_index.json for fast search.
    """
    try:
        user_sector_dir = os.path.join(history_dir, "user_data", username, sector_name)
        os.makedirs(user_sector_dir, exist_ok=True)

        # Sanitize filename
        safe_name = re.sub(r'[^\w\s\.-]', '', filename).strip().replace(" ", "_")
        if not safe_name.endswith('.md'):
            safe_name += ".md"

        full_path = os.path.join(user_sector_dir, safe_name)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # Update sector_index.json
        index_file = os.path.join(user_sector_dir, "sector_index.json")
        index_data = []
        if os.path.exists(index_file):
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
            except:
                index_data = []

        # Remove existing entry if re-uploaded
        index_data = [item for item in index_data if item.get("filename") != safe_name]

        index_data.append({
            "filename": safe_name,
            "original_name": filename,
            "type": doc_type,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "char_count": len(markdown_content),
            "preview": markdown_content[:200]
        })

        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2)

        return full_path
    except Exception as e:
        print(f"Error saving sector document: {e}")
        return None

def search_sector_documents(history_dir, username, sector_name, query, max_results=5):
    """
    Searches across all converted Markdown documents and text files in a user's sector.
    Returns matched snippets with filenames and context.
    """
    user_sector_dir = os.path.join(history_dir, "user_data", username, sector_name)
    if not os.path.exists(user_sector_dir):
        return []

    query_lower = query.lower().strip()
    query_words = [w for w in re.split(r'\s+', query_lower) if len(w) > 2]
    if not query_words:
        query_words = [query_lower]

    results = []

    try:
        for fname in os.listdir(user_sector_dir):
            if fname == "sector_index.json" or fname == "task_history.json":
                continue
            fpath = os.path.join(user_sector_dir, fname)
            if not os.path.isfile(fpath):
                continue

            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                content_lower = content.lower()
                matches_found = []

                # Paragraph-level search
                paragraphs = content.split("\n\n")
                for p in paragraphs:
                    p_clean = p.strip()
                    if not p_clean:
                        continue
                    p_lower = p_clean.lower()
                    score = sum(1 for w in query_words if w in p_lower)
                    if score > 0:
                        matches_found.append({"text": p_clean, "score": score})

                if matches_found:
                    matches_found.sort(key=lambda x: x["score"], reverse=True)
                    top_snippets = [m["text"] for m in matches_found[:2]]
                    results.append({
                        "filename": fname,
                        "match_count": len(matches_found),
                        "snippets": top_snippets
                    })
            except:
                continue

        results.sort(key=lambda x: x["match_count"], reverse=True)
        return results[:max_results]
    except Exception as e:
        print(f"Error searching sector documents: {e}")
        return []
