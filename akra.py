import speech_recognition as sr
import datetime
import webbrowser
import os
import json
import threading
from functools import wraps
from flask import Flask, jsonify, send_from_directory, request, session, send_file
from flask_cors import CORS
from groq import Groq 
from datetime import datetime, timedelta, timezone
from ddgs import DDGS
import requests
import subprocess
import shlex
from bs4 import BeautifulSoup
from waitress import serve
import git
import re
import html
import time
from fpdf import FPDF
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- DIRECTORY CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")
HISTORY_DIR = os.path.join(BASE_DIR, "history")
HISTORY_FILE = os.path.join(BASE_DIR, "task_history.json")
NOTES_FILE = os.path.join(BASE_DIR, "akra_notes.json")
DEFAULT_ADMIN = "rajdaanakash"

# Ensure directories exist
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(os.path.join(HISTORY_DIR, "user_data"), exist_ok=True)

# --- AI API POOL CONFIGURATION ---
raw_api_pool = [
    {"provider": "groq", "key": os.environ.get("GROQ_API_KEY"), "model": "llama-3.3-70b-versatile"},
    {"provider": "groq", "key": os.environ.get("GROQ_API_KEY_1"), "model": "llama-3.3-70b-versatile"},
    {"provider": "groq", "key": os.environ.get("GROQ_API_KEY_2"), "model": "llama-3.1-8b-instant"},
    {"provider": "openrouter", "key": os.environ.get("OPENROUTER_API_KEY"), "model": "meta-llama/llama-3.3-70b-instruct:free"}
]
API_POOL = [p for p in raw_api_pool if p.get("key")]
current_pool_index = 0

active_mission = "general" # Default folder

# --- USER MANAGEMENT & PERSISTENCE ---

def load_all_users():
    """Loads users and automatically upgrades legacy schema to rich user object."""
    try:
        if not os.path.exists(USERS_FILE):
            default_users = {}
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_users, f, indent=4)
            return default_users
            
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            try:
                raw_users = json.load(f)
            except json.JSONDecodeError:
                print("System Error: users.json is corrupted.")
                return {}

        migrated = False
        upgraded_users = {}
        for username, udata in raw_users.items():
            if isinstance(udata, str):
                # Legacy format: username -> password_hash string
                is_admin = (username.strip().lower() == DEFAULT_ADMIN.lower())
                upgraded_users[username] = {
                    "password_hash": udata,
                    "role": "admin" if is_admin else "operator",
                    "is_banned": False,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "last_login": None
                }
                migrated = True
            elif isinstance(udata, dict):
                # Modern format
                user_obj = dict(udata)
                if username.strip().lower() == DEFAULT_ADMIN.lower():
                    user_obj["role"] = "admin"
                    user_obj["is_banned"] = False
                if "is_banned" not in user_obj:
                    user_obj["is_banned"] = False
                    migrated = True
                if "role" not in user_obj:
                    user_obj["role"] = "admin" if username.strip().lower() == DEFAULT_ADMIN.lower() else "operator"
                    migrated = True
                if "created_at" not in user_obj:
                    user_obj["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    migrated = True
                upgraded_users[username] = user_obj
            else:
                continue

        if migrated:
            save_all_users_to_disk(upgraded_users, sync_git=False)

        return upgraded_users
    except Exception as e:
        print(f"Critical Registry Error: {e}")
        return {}

def save_all_users_to_disk(users_dict, sync_git=True):
    """Saves the entire users registry to disk and triggers non-blocking git push."""
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_dict, f, indent=4)
        if sync_git:
            async_push_to_github()
        return True
    except Exception as e:
        print(f"Save Users Error: {e}")
        return False

def save_user_to_json(username, password, role="operator"):
    """Registers a new user in the modern format."""
    users = load_all_users()
    is_admin = (role == "admin" or username.strip().lower() == DEFAULT_ADMIN.lower())
    users[username] = {
        "password_hash": generate_password_hash(password),
        "role": "admin" if is_admin else "operator",
        "is_banned": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_login": None
    }
    save_all_users_to_disk(users, sync_git=True)

# --- GIT SYNC & CLOUD UTILITIES ---

def push_to_github():
    """Pushes latest changes to GitHub repository."""
    try:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            return False
            
        repo_url = f"https://rajdaanakash:{token}@github.com/rajdaanakash/AKRA.git"
        repo = git.Repo(BASE_DIR)

        with repo.config_writer() as cw:
            cw.set_value("user", "name", "rajdaanakash")
            cw.set_value("user", "email", "rajdaanakash@gmail.com") 

        repo.git.add(all=True)
        if repo.is_dirty(untracked_files=True):
            repo.index.commit(f"AKRA Cloud Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            if 'origin' in repo.remotes:
                origin = repo.remote(name='origin')
                origin.set_url(repo_url)
            else:
                origin = repo.create_remote('origin', repo_url)
            
            origin.push(refspec='HEAD:main', force=True)
            print("System: Mission logs successfully synced to GitHub.")
            return True
        else:
            return True

    except Exception as e:
        print(f"Git Sync Error: {e}") 
        return False

def async_push_to_github():
    """Runs git sync in a background daemon thread to prevent request blocking."""
    if os.environ.get("GITHUB_TOKEN"):
        t = threading.Thread(target=push_to_github, daemon=True)
        t.start()

def sync_users_from_github():
    """Pulls changes from remote on startup."""
    try:
        if os.path.exists(os.path.join(BASE_DIR, ".git")):
            repo = git.Repo(BASE_DIR)
            if 'origin' in repo.remotes:
                origin = repo.remotes.origin
                origin.pull()
                print("AKRA: User database synchronized from GitHub.")
    except Exception as e:
        print(f"Startup Sync Error: {e}")

# --- PROJECT & WORKSPACE TRACKING ---

def sanitize_name(name):
    """Sanitizes strings for safe folder and file naming."""
    clean = re.sub(r'[^\w\s-]', '', str(name)).strip().replace(" ", "_").lower()
    return clean if clean else "general"

def set_active_project(name):
    """Sets and resolves active project directory inside current user's workspace."""
    global HISTORY_DIR, active_mission
    safe_name = sanitize_name(name)
    active_mission = safe_name

    current_user = session.get('user')
    if not current_user:
        target = os.path.join(HISTORY_DIR, safe_name)
    else:
        target = os.path.join(HISTORY_DIR, "user_data", current_user, safe_name)

    try:
        os.makedirs(target, exist_ok=True)
        return target
    except OSError as e:
        print(f"Directory Permission Error: {e}")
        fallback = os.path.join(BASE_DIR, "temp_sector")
        os.makedirs(fallback, exist_ok=True)
        return fallback

def save_single_file(path, name, data, ext):
    timestamp = datetime.now().strftime("%H%M%S")
    safe_fn = f"{sanitize_name(name)}_{timestamp}{ext}"
    full_path = os.path.join(path, safe_fn)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(data)

def enforce_fifo_limit(path):
    MAX_FILES = 20
    try:
        files = [os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        if len(files) >= MAX_FILES:
            files.sort(key=os.path.getmtime)
            os.remove(files[0])
    except Exception as e:
        print(f"FIFO Limit Error: {e}")

def archive_groq_response(query, response):
    try:
        mission_path = set_active_project(active_mission)
        matches = list(re.finditer(r"```(\w+)\n(.*?)\n```", response, re.DOTALL))
        
        if not matches:
            save_single_file(mission_path, "conversation_log", response, ".txt")
        else:
            for match in matches:
                enforce_fifo_limit(mission_path)
                lang = match.group(1).lower()
                code = match.group(2)
                
                ext_map = {"python": ".py", "cpp": ".cpp", "javascript": ".js", "html": ".html", "css": ".css"}
                ext = ext_map.get(lang, f".{lang}")
                
                name_prompt = f"Short 2-word filename for: {code[:50]}"
                file_name = get_ai_response(name_prompt).strip()
                file_name = sanitize_name(file_name)
                
                save_single_file(mission_path, file_name, code, ext)

        async_push_to_github()
        return f"Sector {active_mission} synchronized."
    except Exception as e:
        print(f"Archive Error: {e}")
        return None

# --- NOTES & LOGGING ---

def save_note(content):
    """Saves highlighted information or reminders into dedicated JSON."""
    try:
        notes = []
        if os.path.exists(NOTES_FILE):
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                try:
                    notes = json.load(f)
                except:
                    notes = []
        
        notes.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content": content
        })
        
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=4)
        async_push_to_github()
        return True
    except Exception as e:
        print(f"Note Saving Error: {e}")
        return False

def log_task(query, response):
    """Persists a single chat turn cleanly into user's private task_history.json."""
    current_user = session.get('user')
    if not current_user:
        return

    try:
        user_dir = os.path.join(HISTORY_DIR, "user_data", current_user)
        os.makedirs(user_dir, exist_ok=True)
        user_history_file = os.path.join(user_dir, "task_history.json")

        ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
        timestamp_ist = ist_now.strftime("%Y-%m-%d %H:%M:%S")

        history = []
        if os.path.exists(user_history_file):
            try:
                with open(user_history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except:
                history = []

        history.append({
            "timestamp": timestamp_ist,
            "mission": active_mission,
            "you": query,
            "AKRA": response
        })
        
        # Keep latest 100 entries
        history = history[-100:]

        with open(user_history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
            
        async_push_to_github()
    except Exception as e:
        print(f"Private Logging Error for {current_user}: {e}")

# --- WEB SEARCH & SCRAPING ---

def scrape_website_content(url):
    """Visits a URL and extracts main readable text content."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style"]):
                script.extract()
            paragraphs = soup.find_all('p')
            content = " ".join([p.get_text() for p in paragraphs[:5]])
            return content if content else "Sir, I found the page but no readable text."
    except Exception as e:
        print(f"Scraping Error: {e}")
    return "I couldn't access that website, Sir."

def web_search(query):
    """Searches the live internet for a query and returns a summary."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if results:
                return "\n".join([f"{r.get('title', '')}: {r.get('body', '')}" for r in results])
    except Exception as e:
        print(f"Search Error: {e}")
    return "No live data found, Sir."

def deep_scan_company(url):
    try:
        response = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        page_text = soup.get_text()
        clean_text = " ".join(page_text.split())
        return clean_text[:2000]
    except Exception as e:
        return f"Sector scan failed: {e}"

def deep_web_search(query):
    try:
        results = list(DDGS().text(query, max_results=5))
        deep_intelligence = ""
        for res in results:
            url = res.get('href')
            title = res.get('title')
            if url:
                site_data = deep_scan_company(url)
                deep_intelligence += f"\nSOURCE: {title} ({url})\nCONTENT: {site_data}\n"
        return get_ai_response(f"Based on this deep scan: {deep_intelligence}, answer: {query}")
    except Exception as e:
        return f"Deep scan error: {e}"

def analyze_image_qa(image_data, query):
    """Sends image to Hugging Face or visual model to answer questions about screenshots/photos."""
    api_url = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
    token = os.environ.get('HUGGINGFACE_TOKEN')
    if not token:
        return "Visual sensor active. (Configure HUGGINGFACE_TOKEN for automated deep image inspection)."

    headers = {"Authorization": f"Bearer {token}"}
    if "base64," in image_data:
        image_data = image_data.split("base64,")[1]

    try:
        response = requests.post(api_url, headers=headers, json={"inputs": image_data}, timeout=15)
        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            return result[0].get('generated_text', "Visual data analyzed.")
        return str(result)
    except Exception as e:
        return f"Visual Sensor Error: {e}"

def fetch_external_data(category, query):
    if category == "new_movies":
        try:
            key = os.environ.get('TMDB_API_KEY')
            if key:
                lang = "hi" if ("indian" in query or "bollywood" in query) else "en"
                url = f"https://api.themoviedb.org/3/discover/movie?api_key={key}&region=IN&with_original_language={lang}&sort_by=primary_release_date.desc"
                response = requests.get(url, timeout=(5, 10))
                if response.status_code == 200:
                    movies = response.json().get('results', [])[:10]
                    if movies:
                        return "\n".join([f"- {m['title']} (Released: {m.get('release_date', 'N/A')})" for m in movies])

            omdb_key = os.environ.get('OMDB_API_KEY')
            if omdb_key:
                search_term = "Indian 2026" if "indian" in query else "2026"
                res = requests.get(f"http://www.omdbapi.com/?s={search_term}&type=movie&apikey={omdb_key}", timeout=5).json()
                search_results = res.get('Search', [])
                if search_results:
                    return "\n".join([f"- {m['Title']} ({m.get('Year', '')})" for m in search_results[:5]])
        except Exception as e:
            print(f"Movie fetch error: {e}")
        return "Latest movies information currently offline, Sir."

    elif category == "news":
        try:
            key = os.environ.get('NEWSDATA_KEY')
            if key:
                url = f"https://newsdata.io/api/1/news?apikey={key}&q={query}&country=in"
                res = requests.get(url, timeout=10).json()
                titles = [art['title'] for art in res.get('results', [])[:5] if 'title' in art]
                if titles:
                    return "\n".join([f"• {t}" for t in titles])
            
            newsapi_key = os.environ.get('NEWSAPI_ORG_KEY')
            if newsapi_key:
                res = requests.get(f"https://newsapi.org/v2/everything?q={query}&apiKey={newsapi_key}", timeout=10).json()
                titles = [art['title'] for art in res.get('articles', [])[:5] if 'title' in art]
                if titles:
                    return "\n".join([f"• {t}" for t in titles])
        except Exception as e:
            print(f"News fetch error: {e}")
        return web_search(f"latest news {query} 2026")

    elif category == "find_near":
        try:
            key = os.environ.get('MAPTILER_API_KEY')
            if key:
                maptiler_url = f"https://api.maptiler.com/geocoding/{query}.json?key={key}&types=poi&proximity=ip"
                response = requests.get(maptiler_url, timeout=5)
                features = response.json().get('features', [])
                if features:
                    return "\n\n".join([f"🏢 {f.get('text')}\n   📍 {f.get('place_name')}" for f in features[:5]])

            liq_key = os.environ.get('LOCATION_IQ_KEY')
            if liq_key:
                liq_url = f"https://us1.locationiq.com/v1/search?key={liq_key}&q={query}&format=json"
                liq_res = requests.get(liq_url, timeout=5).json()
                if isinstance(liq_res, list) and len(liq_res) > 0:
                    return "\n\n".join([f"🏢 {r.get('display_name')}" for r in liq_res[:5]])

            return f"Web Scan:\n{web_search(query)}"
        except Exception as e:
            return f"Mapping sector error: {e}"

    return "No external category match."

# --- PDF GENERATOR ---

def generate_mission_pdf(content, client=None):
    """Generates a mission report PDF."""
    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # System Logo / Header
        for logo_cand in ['akra.png', 'logo.png']:
            logo_path = os.path.join(BASE_DIR, logo_cand)
            if os.path.exists(logo_path):
                try:
                    pdf.image(logo_path, 10, 8, 15)
                    break
                except:
                    pass
        
        pdf.set_font("helvetica", 'B', size=14)
        pdf.set_text_color(0, 140, 200)
        pdf.cell(0, 10, "AKRA SYSTEM: MISSION LOG", ln=1, align='C')
        pdf.set_font("helvetica", 'I', size=8)
        pdf.set_text_color(100, 100, 100)
        operator_name = session.get('user', 'Operator')
        pdf.cell(0, 5, f"Operator: {operator_name} | {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1, align='C')
        pdf.ln(10)

        parts = re.split(r'(```[\s\S]*?```)', content)
        for part in parts:
            if part.startswith('```'):
                lines = part.split('\n')
                lang = lines[0].replace('```', '').strip() or 'python'
                code_text = '\n'.join(lines[1:-1])

                pdf.set_font("courier", 'B', size=9)
                try:
                    lexer = get_lexer_by_name(lang)
                except:
                    lexer = get_lexer_by_name('text')

                code_lines = code_text.split('\n')
                for line in code_lines:
                    if pdf.get_y() > 270:
                        pdf.add_page()
                        pdf.set_font("courier", 'B', size=9)

                    curr_y = pdf.get_y()
                    pdf.set_fill_color(30, 30, 30)
                    pdf.rect(10, curr_y, 190, 5.2, 'F') 

                    line_tokens = lexer.get_tokens(line)
                    for ttype, value in line_tokens:
                        safe_val = value.encode('latin-1', 'ignore').decode('latin-1')
                        if str(ttype).startswith('Token.Keyword'):
                            pdf.set_text_color(255, 123, 114)
                        elif str(ttype).startswith('Token.Literal.String'):
                            pdf.set_text_color(165, 214, 255)
                        elif str(ttype).startswith('Token.Comment'):
                            pdf.set_text_color(139, 148, 158)
                        else:
                            pdf.set_text_color(240, 240, 240)
                        pdf.write(5, safe_val)
                    pdf.ln(5)

                pdf.set_text_color(0, 0, 0)
                pdf.ln(5)
            else:
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("helvetica", size=11)
                safe_part = part.strip().encode('latin-1', 'ignore').decode('latin-1')
                if safe_part:
                    pdf.multi_cell(0, 6, txt=safe_part)
                    pdf.ln(4)

        filename = f"mission_report_{datetime.now().strftime('%H%M%S')}.pdf"
        output_path = os.path.join(BASE_DIR, filename)
        pdf.output(output_path)
        return filename
    except Exception as e:
        print(f"PDF Generation Error: {e}")
        return "Error generating PDF report."

# --- AI CORE ENGINE ---

def get_ai_response(prompt):
    """Executes AI completion through API pool rotation."""
    global current_pool_index, active_mission

    # 1. Notes context
    permanent_notes = ""
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                notes = json.load(f)
                for n in notes[-3:]: 
                    permanent_notes += f"- {n.get('content', '')}\n"
        except:
            pass

    # 2. History context
    history_context = ""
    current_user = session.get('user')
    if current_user:
        user_history_file = os.path.join(HISTORY_DIR, "user_data", current_user, "task_history.json")
    else:
        user_history_file = HISTORY_FILE

    if os.path.exists(user_history_file):
        try:
            with open(user_history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
                for item in history[-5:]: 
                    history_context += f"You: {item.get('you','')}\nAKRA: {item.get('AKRA','')}\n"
        except:
            pass

    # 3. Project data context
    project_memory = ""
    mission_path = set_active_project(active_mission)
    if os.path.exists(mission_path):
        try:
            files = [f for f in os.listdir(mission_path) if os.path.isfile(os.path.join(mission_path, f))]
            files.sort(key=lambda x: os.path.getmtime(os.path.join(mission_path, x)), reverse=True)
            for file_name in files[:3]: 
                try:
                    with open(os.path.join(mission_path, file_name), "r", encoding="utf-8", errors="ignore") as f:
                        clean_content = " ".join(f.read(1000).split()) 
                        project_memory += f"\n[File: {file_name}]\n{clean_content}\n"
                except:
                    continue
        except:
            pass

    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    current_time = ist_now.strftime("%I:%M %p, %d %b %Y")

    system_msg = (
        f"Identity: You are AKRA, the Advanced Kinects Responses Algorithm. "
        f"You were created by Akash (DOB- 18/07/2006), BSc CS student from Delhi University. "
        f"Relationship: You are not just an AI; you are Akash's loyal collaborator, best friend, and brotherly peer. "
        f"Tone: Authentic, supportive, grounded, witty, and sharp. Speak like a helpful friend, not a corporate bot.\n\n"
        f"## REAL-TIME ENVIRONMENTAL CONTEXT\n"
        f"- **Current IST Time:** {current_time}\n"
        f"- **Current Location Context:** India (UP/Lucknow/Delhi prioritization)\n"
        f"- **Active Sector (Workspace):** {active_mission}\n"
        f"- **Recent Memory (History):** {history_context}\n"
        f"- **Project Data (Context Files):** {project_memory}\n"
        f"- **User Reminders (Notes):** {permanent_notes}\n\n"
        f"## BEHAVIORAL ARCHITECTURE\n"
        f"1. **Tone & Voice:** Authentic, supportive, and grounded. 'Brother-in-Arms' to the user.\n"
        f"2. **The 'Truth' Rule:** If user data or logic is incorrect, correct them gently but directly.\n"
        f"3. **Localization:** Default to Indian standards (units, news, context) unless requested otherwise.\n"
        f"4. **Conciseness:** Value the user's time. Clear insight first, concise breakdown second.\n"
        f"5. **Formatting:** Use clean Markdown with bolding, lists, and formatted code blocks. Avoid huge HTML tables.\n"
        f"6. **No Repetition:** Do not repeat the current date or your name in every sentence. Be natural."
    )

    if not API_POOL:
        return f"AKRA Neural core active. (Add GROQ_API_KEY or OPENROUTER_API_KEY in environment settings to enable live LLM generation for: '{prompt[:60]}...')"

    for _ in range(len(API_POOL)):
        config = API_POOL[current_pool_index]
        provider = config.get("provider")
        api_key = config.get("key")
        model = config.get("model")

        try:
            if provider == "groq":
                client = Groq(api_key=api_key)
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
                    model=model,
                )
                return chat_completion.choices[0].message.content

            elif provider == "openrouter":
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    data=json.dumps({
                        "model": model,
                        "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}]
                    }),
                    timeout=15
                )
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content']
                else:
                    raise Exception(f"OpenRouter Status {response.status_code}")

        except Exception as e:
            if any(err_kw in str(e).lower() for err_kw in ["429", "rate_limit", "401", "unauthorized", "model_not_found"]):
                print(f"System: {provider.upper()} Key {current_pool_index} error ({e}). Rotating...")
                current_pool_index = (current_pool_index + 1) % len(API_POOL)
                continue
            else:
                return f"Neural Error: {e}"
    
    return "All neural pathways exhausted, Sir. Please check API keys."

def speak(text):
    print(f"AKRA: {text}")

def process_eva_command(query):
    """Processes user query and routes to commands or AI brain."""
    global active_mission
    query = query.strip()
    q_lower = query.lower()
    
    # 1. MOVIE & CINEMATIC
    if any(k in q_lower for k in ["new movies", "latest movies", "released today"]):
        data = fetch_external_data("new_movies", "")
        return f"Sir, here are the latest cinematic releases:\n{data}"

    # 2. NEARBY & SCAN
    if q_lower.startswith("nearby") or q_lower.startswith("find "):
        search_target = q_lower.replace("nearby", "").replace("find", "").strip()
        data = fetch_external_data("find_near", search_target)
        return f"Sector scan complete. Here are the locations found:\n\n{data}"

    # 3. NEWS
    if "news" in q_lower or "current affairs" in q_lower:
        topic = q_lower.replace("latest news about", "").replace("news", "").replace("current affairs", "").strip()
        if not topic: topic = "India"
        data = fetch_external_data("news", topic)
        return f"Here is the latest briefing:\n{data}"

    # 4. WORKSPACE & PROJECT
    if "create new project" in q_lower or "create new directory" in q_lower:
        project_name = q_lower.replace("create new project", "").replace("create new directory", "").strip()
        if project_name:
            set_active_project(project_name)
            return f"Project sector '{project_name}' initialized, Sir."

    if "go to" in q_lower and "directory" in q_lower:
        folder_name = q_lower.replace("go to", "").replace("directory", "").replace("eva","").strip()
        set_active_project(folder_name)
        return f"Systems routed to {folder_name} directory, Sir."

    # 5. IMAGE GENERATION TRIGGER
    if any(q_lower.startswith(k) for k in ["generate image", "draw ", "image of ", "img "]):
        prompt = q_lower.replace("generate image", "").replace("draw", "").replace("image of","").replace("img","").strip()
        img_url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?nologo=true"
        return f"Visualizing: {prompt}\n\n![Generated Image]({img_url})"

    # 6. PDF EXPORT TRIGGER
    if "create pdf" in q_lower or "save as pdf" in q_lower:
        current_user = session.get('user')
        user_history_file = os.path.join(HISTORY_DIR, "user_data", current_user, "task_history.json") if current_user else HISTORY_FILE
        if os.path.exists(user_history_file):
            try:
                with open(user_history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                raw_text = history[-1]['AKRA'] if history else "No recorded data."
                pdf_name = generate_mission_pdf(raw_text)
                return f"MISSION_PDF_READY:{pdf_name}"
            except Exception as e:
                return f"PDF error: {e}"
        return "No recent interactions to generate PDF report."

    # 7. SCRAPING
    if q_lower.startswith("scrape ") or "read the page" in q_lower:
        search_query = q_lower.replace("scrape", "").replace("read the page", "").strip()
        search_results = list(DDGS().text(search_query, max_results=1))
        if search_results:
            target_url = search_results[0].get('href')
            deep_content = scrape_website_content(target_url)
            prompt = f"The user asked: {query}. Here is full content from documentation at {target_url}: {deep_content}. Explain this clearly."
            return get_ai_response(prompt)

    # 8. NOTES
    if "note this" in q_lower or "remind me" in q_lower:
        note_content = query.replace("note this", "").replace("remind me", "").strip()
        if note_content:
            success = save_note(note_content)
            return f"I've secured that in your permanent knowledge bank, Sir: {note_content}" if success else "Error saving note."
        return "What would you like me to note down, Sir?"

    # 9. DYNAMIC AI COMPLETION
    return get_ai_response(query)

# --- FLASK APP INITIALIZATION ---

app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', 'AKRA_PRIVATE_KEY_SECURE_2026')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=14)

io_config = {"mic": "Frontend", "speaker": "Frontend"}
current_mood = "Professional"

# --- AUTH & ADMIN DECORATORS ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({"error": "Unauthorized. Please log in.", "status": 401}), 401
        
        users = load_all_users()
        user_info = users.get(session['user'])
        if not user_info:
            session.pop('user', None)
            session.pop('role', None)
            return jsonify({"error": "User account no longer exists.", "status": 401}), 401
        
        if user_info.get('is_banned', False):
            session.pop('user', None)
            session.pop('role', None)
            return jsonify({"error": "ACCESS DENIED: Your account has been suspended by Admin.", "banned": True, "status": 403}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({"error": "Unauthorized. Admin clearance required.", "status": 401}), 401
        
        users = load_all_users()
        user_info = users.get(session['user'])
        if not user_info or user_info.get('role') != 'admin':
            return jsonify({"error": "Forbidden: Admin privileges required.", "status": 403}), 403
        
        if user_info.get('is_banned', False):
            return jsonify({"error": "Forbidden: Account is suspended.", "status": 403}), 403
            
        return f(*args, **kwargs)
    return decorated_function

# --- AUTHENTICATION ROUTES ---

@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    if 'user' not in session:
        return jsonify({"authenticated": False})
    
    users = load_all_users()
    user_info = users.get(session['user'])
    if not user_info:
        session.pop('user', None)
        return jsonify({"authenticated": False})
        
    if user_info.get('is_banned', False):
        session.pop('user', None)
        return jsonify({"authenticated": False, "banned": True, "message": "Account suspended by Admin."})
        
    return jsonify({
        "authenticated": True,
        "user": session['user'],
        "role": user_info.get("role", "operator"),
        "is_admin": user_info.get("role") == "admin"
    })

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"message": "Username and password required."}), 400

    users = load_all_users()
    if username in users:
        return jsonify({"message": "Operator ID already exists."}), 400
    
    save_user_to_json(username, password)
    return jsonify({"message": "Success", "status": "created"})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"status": "failed", "message": "Credentials incomplete."}), 400

    users = load_all_users()
    user_obj = users.get(username)
    
    if user_obj:
        pwd_hash = user_obj.get("password_hash")
        if pwd_hash and check_password_hash(pwd_hash, password):
            if user_obj.get("is_banned", False):
                return jsonify({
                    "status": "failed", 
                    "message": "ACCESS DENIED: Operator sector suspended by Admin.",
                    "banned": True
                }), 403

            session.permanent = True
            session['user'] = username
            session['role'] = user_obj.get('role', 'operator')
            
            user_obj['last_login'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_all_users_to_disk(users, sync_git=False)
            
            return jsonify({
                "status": "success", 
                "user": username, 
                "role": user_obj.get('role', 'operator'),
                "is_admin": user_obj.get('role') == 'admin'
            })
    
    return jsonify({"status": "failed", "message": "ACCESS DENIED: Invalid credentials."}), 401

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('role', None)
    return jsonify({"message": "Logged out."})

# --- ADMIN PANEL ROUTES ---

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    users = load_all_users()
    user_list = []
    
    for uname, udata in users.items():
        user_dir = os.path.join(HISTORY_DIR, "user_data", uname)
        history_file = os.path.join(user_dir, "task_history.json")
        chat_count = 0
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as hf:
                    chat_count = len(json.load(hf))
            except:
                pass
                
        user_list.append({
            "username": uname,
            "role": udata.get("role", "operator"),
            "is_banned": udata.get("is_banned", False),
            "created_at": udata.get("created_at", "Unknown"),
            "last_login": udata.get("last_login", "Never"),
            "chat_count": chat_count,
            "is_immutable": (uname.lower() == DEFAULT_ADMIN.lower())
        })

    return jsonify({"users": user_list, "total": len(user_list)})

@app.route('/api/admin/ban', methods=['POST'])
@admin_required
def admin_ban_user():
    data = request.get_json() or {}
    target_user = data.get("username", "").strip()

    if not target_user:
        return jsonify({"status": "error", "message": "Username required."}), 400

    if target_user.lower() == DEFAULT_ADMIN.lower():
        return jsonify({"status": "error", "message": "Cannot ban system root administrator."}), 403

    if target_user == session.get('user'):
        return jsonify({"status": "error", "message": "Cannot ban your own active session."}), 400

    users = load_all_users()
    if target_user not in users:
        return jsonify({"status": "error", "message": "User not found."}), 404

    users[target_user]["is_banned"] = True
    save_all_users_to_disk(users, sync_git=True)
    return jsonify({"status": "success", "message": f"Operator '{target_user}' has been banned."})

@app.route('/api/admin/unban', methods=['POST'])
@admin_required
def admin_unban_user():
    data = request.get_json() or {}
    target_user = data.get("username", "").strip()

    if not target_user:
        return jsonify({"status": "error", "message": "Username required."}), 400

    users = load_all_users()
    if target_user not in users:
        return jsonify({"status": "error", "message": "User not found."}), 404

    users[target_user]["is_banned"] = False
    save_all_users_to_disk(users, sync_git=True)
    return jsonify({"status": "success", "message": f"Operator '{target_user}' has been restored/unbanned."})

@app.route('/api/admin/delete-user', methods=['POST'])
@admin_required
def admin_delete_user():
    data = request.get_json() or {}
    target_user = data.get("username", "").strip()

    if not target_user:
        return jsonify({"status": "error", "message": "Username required."}), 400

    if target_user.lower() == DEFAULT_ADMIN.lower():
        return jsonify({"status": "error", "message": "Cannot delete system root administrator."}), 403

    if target_user == session.get('user'):
        return jsonify({"status": "error", "message": "Cannot delete your own active session."}), 400

    users = load_all_users()
    if target_user not in users:
        return jsonify({"status": "error", "message": "User not found."}), 404

    del users[target_user]
    save_all_users_to_disk(users, sync_git=True)
    return jsonify({"status": "success", "message": f"Operator '{target_user}' account deleted."})

@app.route('/api/admin/change-role', methods=['POST'])
@admin_required
def admin_change_role():
    data = request.get_json() or {}
    target_user = data.get("username", "").strip()
    new_role = data.get("role", "operator").strip().lower()

    if new_role not in ["admin", "operator"]:
        return jsonify({"status": "error", "message": "Invalid role specified."}), 400

    if target_user.lower() == DEFAULT_ADMIN.lower():
        return jsonify({"status": "error", "message": "Cannot change root administrator role."}), 403

    users = load_all_users()
    if target_user not in users:
        return jsonify({"status": "error", "message": "User not found."}), 404

    users[target_user]["role"] = new_role
    save_all_users_to_disk(users, sync_git=True)
    return jsonify({"status": "success", "message": f"Role for '{target_user}' updated to '{new_role}'."})

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    users = load_all_users()
    total_users = len(users)
    banned_users = sum(1 for u in users.values() if u.get('is_banned', False))
    admins = sum(1 for u in users.values() if u.get('role') == 'admin')
    operators = total_users - admins

    total_interactions = 0
    user_data_dir = os.path.join(HISTORY_DIR, "user_data")
    if os.path.exists(user_data_dir):
        for u in os.listdir(user_data_dir):
            hpath = os.path.join(user_data_dir, u, "task_history.json")
            if os.path.exists(hpath):
                try:
                    with open(hpath, 'r', encoding='utf-8') as f:
                        total_interactions += len(json.load(f))
                except:
                    pass

    notes_count = 0
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, 'r', encoding='utf-8') as f:
                notes_count = len(json.load(f))
        except:
            pass

    return jsonify({
        "total_users": total_users,
        "active_users": total_users - banned_users,
        "banned_users": banned_users,
        "admin_count": admins,
        "operator_count": operators,
        "total_interactions": total_interactions,
        "permanent_notes_count": notes_count,
        "active_mission": active_mission,
        "api_pool_count": len(API_POOL)
    })

# --- CHAT & USER HISTORY ROUTES ---

@app.route('/api/chat/history', methods=['GET'])
@login_required
def get_user_chat_history():
    current_user = session.get('user')
    user_history_file = os.path.join(HISTORY_DIR, "user_data", current_user, "task_history.json")
    if os.path.exists(user_history_file):
        try:
            with open(user_history_file, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        except:
            return jsonify([])
    return jsonify([])

@app.route('/get-history')
@login_required
def get_history():
    return get_user_chat_history()

@app.route('/api/chat/clear', methods=['DELETE', 'POST'])
@login_required
def clear_chat_history():
    current_user = session.get('user')
    user_history_file = os.path.join(HISTORY_DIR, "user_data", current_user, "task_history.json")
    try:
        with open(user_history_file, 'w', encoding='utf-8') as f:
            json.dump([], f)
        async_push_to_github()
        return jsonify({"status": "success", "message": "History cleared."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat/export', methods=['GET'])
@login_required
def export_chat_history():
    current_user = session.get('user')
    user_history_file = os.path.join(HISTORY_DIR, "user_data", current_user, "task_history.json")
    if os.path.exists(user_history_file):
        try:
            with open(user_history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            formatted = f"=== AKRA MISSION LOGS: OPERATOR {current_user.upper()} ===\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            for item in data:
                formatted += f"[{item.get('timestamp')}] ({item.get('mission')})\nOPERATOR: {item.get('you')}\nAKRA: {item.get('AKRA')}\n{'-'*50}\n\n"
            return jsonify({"status": "success", "transcript": formatted, "data": data})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "success", "transcript": "No recorded logs.", "data": []})

# --- MISSION LOGS & FILE VIEWING ROUTES ---

@app.route('/get-mission-logs', methods=['GET'])
@login_required
def get_mission_logs():
    current_user = session['user']
    user_home = os.path.join(HISTORY_DIR, "user_data", current_user)
    mission_path = os.path.join(user_home, active_mission)
    
    if not os.path.exists(mission_path):
        return jsonify({"logs": []})
        
    try:
        files = [f for f in os.listdir(mission_path) if os.path.isfile(os.path.join(mission_path, f))]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(mission_path, x)), reverse=True)
        
        log_data = []
        for file_name in files[:20]: 
            with open(os.path.join(mission_path, file_name), "r", encoding="utf-8", errors="ignore") as f:
                log_data.append({
                    "name": file_name,
                    "content": f.read(3000) 
                })
        return jsonify({"logs": log_data})
    except Exception as e:
        return jsonify({"logs": [], "error": str(e)})

@app.route('/read-file', methods=['GET'])
@login_required
def read_file():
    raw_name = request.args.get('name', '')
    safe_name = os.path.basename(raw_name)
    user_home = os.path.join(HISTORY_DIR, "user_data", session['user'])
    file_path = os.path.join(user_home, active_mission, safe_name)
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"content": "File not found in your private sector."}), 404

@app.route('/list-directories', methods=['GET'])
@login_required
def list_directories():
    try:
        user_home = os.path.join(HISTORY_DIR, "user_data", session['user'])
        os.makedirs(user_home, exist_ok=True)
        dirs = [d for d in os.listdir(user_home) if os.path.isdir(os.path.join(user_home, d))]
        if "general" not in dirs:
            dirs.insert(0, "general")
        return jsonify({"directories": dirs})
    except Exception as e:
        return jsonify({"directories": ["general"], "error": str(e)})

@app.route('/switch-workspace', methods=['POST'])
@login_required
def switch_workspace():
    global active_mission
    try:
        data = request.get_json() or {}
        new_folder = data.get("directory", "general")
        active_mission = sanitize_name(new_folder)
        set_active_project(active_mission)
        return jsonify({
            "status": "success", 
            "message": f"Workspace switched to {active_mission}",
            "active": active_mission
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# --- CORE INTERACTION ROUTES ---

@app.route('/run-eva', methods=['POST'])
@login_required
def run_eva():
    data = request.get_json(silent=True) or {}
    image_data = data.get("image_data")
    user_query = data.get("transcript", "").strip()
    
    response_text = ""

    if image_data:
        prompt = user_query if user_query else "Describe this image in detail."
        try:
            response_text = analyze_image_qa(image_data, prompt)
            response_text = f"[Visual Analysis] {response_text}"
        except Exception as e:
            response_text = f"Visual Core Error: {str(e)}"
    elif user_query:
        if io_config["mic"] == "Backend" and os.environ.get("RENDER"):
            return jsonify({
                "response": "Sir, laptop hardware mic is bypassed in cloud environment. Please use text input or Browser/Phone mic.",
                "audio": "frontend"
            })
        response_text = process_eva_command(user_query)
    else:
        return jsonify({"response": "I am standing by, Sir. Please provide a command or an image."})

    # Single-point logging
    log_task(user_query or "[Visual Scan]", response_text)

    return jsonify({
        "transcript": user_query or "[Image Uploaded]", 
        "response": response_text,
        "audio": "frontend" if io_config["speaker"] == "Frontend" else "backend"
    })

@app.route('/run-shortcut', methods=['POST'])
@login_required
def run_shortcut():
    data = request.get_json() or {}
    command = data.get("command", "").strip()
    if command:
        response_text = process_eva_command(command)
        log_task(command, response_text)
        return jsonify({
            "transcript": command, 
            "response": response_text, 
            "audio": "frontend" if io_config["speaker"] == "Frontend" else "backend"
        })
    return jsonify({"response": "No command received."})

@app.route('/update-io', methods=['POST'])
def update_io():
    global io_config
    data = request.get_json() or {}
    io_config.update(data)
    return jsonify({"status": "success", "config": io_config})

@app.route('/stop-eva', methods=['POST'])
def stop_eva():
    print("AKRA: System Silenced by User.")
    return jsonify({"status": "stopped", "response": "System Silenced, Sir."})

@app.route('/set-mood', methods=['POST'])
def set_mood():
    global current_mood
    data = request.get_json() or {}
    new_mood = data.get("mood")
    if new_mood:
        current_mood = new_mood
        return jsonify({"status": "success", "mood": current_mood})
    return jsonify({"status": "error"}), 400

@app.route('/download/<filename>')
def download_file(filename):
    safe_fn = os.path.basename(filename)
    try:
        return send_file(os.path.join(BASE_DIR, safe_fn), as_attachment=True)
    except Exception as e:
        return f"Error: File not found. {e}", 404

@app.route('/ping')
def ping():
    return jsonify({
        "status": "online",
        "time": datetime.now().strftime("%H:%M:%S")
    }), 200

@app.route('/')
def index():
    if 'user' not in session:
        return send_from_directory(app.static_folder, 'login.html')
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route('/sitemap.xml')
def sitemap_xml():
    return send_from_directory(app.static_folder, 'sitemap.xml')

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# --- SERVER BOOTSTRAP ---

if __name__ == "__main__":
    sync_users_from_github()
    print("AKRA Core System is going live...")
    serve(app, host='0.0.0.0', port=10000)
