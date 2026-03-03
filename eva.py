import speech_recognition as sr
# import pyttsx3
import datetime
import webbrowser
import os
import json
# import pyautogui 
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from groq import Groq 
from datetime import datetime
from ddgs import DDGS
import requests
import subprocess
import shlex
from bs4 import BeautifulSoup
from waitress import serve
import git
import re
import html
from fpdf import FPDF

# --- CONFIGURATION ---


API_POOL = [
    {"provider": "groq", "key": os.environ.get("GROQ_API_KEY_1"), "model": "llama-3.3-70b-versatile"},
    {"provider": "groq", "key": os.environ.get("GROQ_API_KEY_2"), "model": "llama-3.3-70b-versatile"},
    {"provider": "openrouter", "key": os.environ.get("OPENROUTER_API_KEY"), "model": "openrouter/free"}
]
# Filter out empty keys
API_POOL = [p for p in API_POOL if p["key"]]
current_pool_index = 0

def get_ai_response(prompt):
    global current_pool_index, active_mission
    
    # --- 1. PREPARE ALL DATA FIRST ---
    permanent_notes = ""
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r") as f:
            notes = json.load(f)
            for n in notes[-3:]: 
                permanent_notes += f"- {n['content']}\n"

    history_context = ""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
            for item in history[-5:]: 
                history_context += f"User: {item['user']}\nEVA: {item['eva']}\n"

    # --- NEW: ACTIVE DIRECTORY SCANNER ---
    project_memory = ""
    mission_path = os.path.join(HISTORY_DIR, active_mission)
    
    if os.path.exists(mission_path):
        # We look for the 3 most recently saved codes/logs in this directory
        files = [f for f in os.listdir(mission_path) if os.path.isfile(os.path.join(mission_path, f))]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(mission_path, x)), reverse=True)
        
        for file_name in files[:3]: 
            try:
                with open(os.path.join(mission_path, file_name), "r", encoding="utf-8") as f:
                    # Read only 1000 chars instead of 1500 to stay safe
                    content = f.read(1000) 
                    # Remove extra whitespace/newlines to save space
                    clean_content = " ".join(content.split()) 
                    project_memory += f"\n[File: {file_name}]\n{clean_content}\n"
            except:
                continue

    # Define system_msg with the new Project Memory
    system_msg = (
        f"You are EVA (Enhanced Virtual Assitant), created by Akash in India so provide data in India's point of view and cercumsentence. Current Project: {active_mission}.\n"
        f"Project Files for Context:\n{project_memory}\n"
        f"Permanent Notes:\n{permanent_notes}\n"
        f"Recent Chat:\n{history_context}"
        "STRICT INSTRUCTION: Provide data in clear Markdown format. "
        "Avoid large HTML tables as they lag the system. Use bullet points or Markdown tables instead."
    )

    # --- 2. THE ROTATION LOOP ---
    for _ in range(len(API_POOL)):
        config = API_POOL[current_pool_index]
        provider = config["provider"]
        api_key = config["key"]
        model = config["model"]

        try:
            if provider == "groq":
                # Use Groq Library for Groq keys
                client = Groq(api_key=api_key)
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
                    model=model,
                )
                return chat_completion.choices[0].message.content

            elif provider == "openrouter":
                # Use Requests for OpenRouter keys
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
            # Detect Rate Limits (429) or Errors and Rotate
            if "429" in str(e) or "rate_limit" in str(e).lower() or "Status 401" in str(e):
                print(f"System: {provider.upper()} Key {current_pool_index} failed. Rotating...")
                current_pool_index = (current_pool_index + 1) % len(API_POOL)
                continue 
            else:
                return f"Neural Error: {e}"
    
    return "All neural pathways exhausted, Sir."
                
   

# This finds the EXACT folder where eva.py is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Now we join that with your folders
HISTORY_FILE = os.path.join(BASE_DIR, "task_history.json")
HISTORY_DIR = os.path.join(BASE_DIR, "history", "ai_responses")
NOTES_FILE = os.path.join(BASE_DIR, "eva_notes.json")
# --- NEW: ACTIVE PROJECT TRACKER ---
active_mission = "general" # Default folder


def save_note(content):
    """Saves highlighted information or reminders into a dedicated JSON."""
    try:
        notes = []
        if os.path.exists(NOTES_FILE):
            with open(NOTES_FILE, "r") as f:
                notes = json.load(f)
        
        notes.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content": content
        })
        
        with open(NOTES_FILE, "w") as f:
            json.dump(notes, f, indent=4)
        return True
    except Exception as e:
        print(f"Note Saving Error: {e}")
        return False
    
def push_to_github():
    try:
        token = os.environ.get("GITHUB_TOKEN")
        # Explicitly build the URL with your username and token
        repo_url = f"https://rajdaanakash:{token}@github.com/rajdaanakash/EVA_Enhanced_Virtual_Assistant.git"
        
        repo = git.Repo(BASE_DIR)

        # Set identity signatures
        with repo.config_writer() as cw:
            cw.set_value("user", "name", "rajdaanakash")
            cw.set_value("user", "email", "rajdaanakash@gmail.com") 

        repo.git.add(all=True)
        # Check if there are actually changes to commit to avoid errors
        if repo.is_dirty(untracked_files=True):
            repo.index.commit(f"EVA Cloud Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # CRITICAL: Re-set the remote URL to ensure the token is used for THIS push
            if 'origin' in repo.remotes:
                origin = repo.remote(name='origin')
                origin.set_url(repo_url)
            else:
                origin = repo.create_remote('origin', repo_url)
            
            # Use 'HEAD:main' to tell Render exactly where to push
            origin.push(refspec='HEAD:main', force=True)
            print("System: Mission logs successfully synced to GitHub.")
            return True
        else:
            print("System: No new data to sync.")
            return True

    except Exception as e:
        print(f"Git Sync Error: {e}") 
        return False

def archive_groq_response(query, response):
    try:
        mission_path = os.path.join(HISTORY_DIR, active_mission)
        if not os.path.exists(mission_path):
            os.makedirs(mission_path)

        # 1. FIND ALL BLOCKS (Using finditer instead of search)
        matches = list(re.finditer(r"```(\w+)\n(.*?)\n```", response, re.DOTALL))
        
        # If no code blocks, save the whole text as one log
        if not matches:
            save_single_file(mission_path, "response_log", response, ".txt")
            return "Log saved."

        # 2. SAVE EACH BLOCK INDIVIDUALLY
        for match in matches:
            # Check FIFO limit before every single save
            enforce_fifo_limit(mission_path)
            
            detected_lang = match.group(1).lower()
            save_data = match.group(2)
            
            ext_map = {"python": ".py", "javascript": ".js", "cpp": ".cpp", "html": ".html", "bash": ".sh"}
            ext = ext_map.get(detected_lang, f".{detected_lang}")

            # AI Filename Logic
            name_prompt = f"Suggest a 2-word filename for this: {save_data[:50]}"
            clean_name = get_ai_response(name_prompt).strip().replace(" ", "_").lower()
            clean_name = re.sub(r'[^\w\s-]', '', clean_name)
            
            save_single_file(mission_path, clean_name, save_data, ext)

        return f"Sector {active_mission} updated with {len(matches)} new files."

    except Exception as e:
        print(f"Archive Multi-FIFO Error: {e}")
        return None

# Helper to keep the code clean
def enforce_fifo_limit(path):
    MAX_FILES = 20
    files = [os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    if len(files) >= MAX_FILES:
        files.sort(key=os.path.getmtime)
        os.remove(files[0]) # Delete oldest

def save_single_file(path, name, data, ext):
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"{name}_{timestamp}{ext}"
    with open(os.path.join(path, filename), "w", encoding="utf-8") as f:
        f.write(data)
    
def scrape_website_content(url):
    """Visits a URL and extracts the main text content."""
    try:
        # User-agent makes the request look like it's coming from a real browser
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove scripts and styles that aren't useful text
            for script in soup(["script", "style"]):
                script.extract()

            # Get all paragraph text
            paragraphs = soup.find_all('p')
            content = " ".join([p.get_text() for p in paragraphs[:5]]) # Get first 5 paragraphs
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
                search_data = "\n".join([f"{r['title']}: {r['body']}" for r in results])
                return search_data
    except Exception as e:
        print(f"Search Error: {e}")
    return "No live data found, Sir."

# engine = pyttsx3.init('sapi5')
# voices = engine.getProperty('voices')
# engine.setProperty('voice', voices[1].id) 
# engine.setProperty('rate', 185) 

app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app)

# --- CORE FUNCTIONS ---

def speak(text):
    print(f"EVA: {text}")
    # try:
    #     # Create a local engine instance to avoid threading issues
    #     local_engine = pyttsx3.init()
    #     voices = local_engine.getProperty('voices')
    #     local_engine.setProperty('voice', voices[1].id)
    #     local_engine.setProperty('rate', 185)
        
    #     local_engine.say(text)
    #     local_engine.runAndWait()
    #     local_engine.stop() # Clean up the engine after speaking
    #     del local_engine
    # except Exception as e:
    #     print(f"Voice Error: {e}")

def log_task(query, response):  
    try:
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        
        # Append the new interaction
        history.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": query,
            "eva": response
        })
        
        # --- NEW: FIFO LOGIC (Limit to 2000 lines/entries) ---
        # Since each entry is roughly 5-7 lines in JSON, 
        # we limit the 'number of entries' to keep the total lines manageable.
        MAX_ENTRIES = 100 # 300 entries is roughly 2000 lines in a JSON file
        
        if len(history) > MAX_ENTRIES:
            # Remove the oldest entry (index 0)
            history = history[-MAX_ENTRIES:] 
            print(f"System: FIFO Cleanup performed. Keeping latest {MAX_ENTRIES} entries.")
        # -----------------------------------------------------

        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        print(f"Logging Error: {e}")

def listen():
    # 1. Check if running on Render cloud
    if os.environ.get("RENDER"):
        print("System: Mic bypassed in Cloud environment.")
        return ""

    # 2. Local hardware logic (only runs on your laptop)
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("Listening...")
            r.pause_threshold = 0.8
            audio = r.listen(source)
            query = r.recognize_google(audio, language='en-in')
            print(f"User: {query}")
            return query
    except Exception as e:
        print(f"Mic Error: {e}")
        return ""


def deep_scan_company(url):
    """EVA visits the specific company site to gather deep intelligence"""
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract text from the main sections
        page_text = soup.get_text()
        # Clean up whitespace
        clean_text = " ".join(page_text.split())
        
        return clean_text[:2000] # Feed first 2000 characters to the AI brain
    except Exception as e:
        return f"Sector scan failed: {e}"
    
def deep_web_search(query):
    # 1. Get initial search results
    results = DDGS().text(query, max_results=10)
    
    deep_intelligence = ""
    for res in results:
        url = res.get('href')
        title = res.get('title')
        print(f"System: Deep Scanning {url}...")
        
        # 2. Extract specific webpage content
        site_data = deep_scan_company(url) 
        deep_intelligence += f"\nSOURCE: {title} ({url})\nCONTENT: {site_data}\n"
    
    # 3. Feed the rich data to the AI Brain
    return get_ai_response(f"Based on this deep scan: {deep_intelligence}, answer: {query}")


def set_active_project(name):
    """Creates a new folder for the current project in the history directory."""
    global HISTORY_DIR #
    # Path: history/ai_responses/your_project_name
    project_path = os.path.join(HISTORY_DIR, name) 
    
    if not os.path.exists(project_path):
        os.makedirs(project_path) #
        print(f"System: Created new directory at {project_path}")
    
    return project_path


def analyze_image_qa(image_data, query):
    """Sends image to Hugging Face to answer questions about screenshots/photos"""
    api_url = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
    headers = {"Authorization": f"Bearer {os.environ.get('HUGGINGFACE_TOKEN')}"}
    
    # Clean the base64 string if it comes from the frontend
    if "base64," in image_data:
        image_data = image_data.split("base64,")[1]

    try:
        response = requests.post(api_url, headers=headers, json={"inputs": image_data}, timeout=15)
        result = response.json()
        return result[0].get('generated_text', "Sir, the visual data is blurred. I cannot see clearly.")
    except Exception as e:
        return f"Visual Sensor Error: {e}"

#for current afair and api is used here
def fetch_external_data(category, query):
    tm_out = (5, 15)
    
    # --- MOVIE SECTION ---
    if category == "new_movies":
        try:
            # --- 1. PRIMARY: TMDB Discover (Filters by Nationality) ---
            key = os.environ.get('TMDB_API_KEY')
            
            # Detect nationality from your voice command
            # If you say "Indian", use 'hi' (Hindi); else default to 'en' (Hollywood)
            lang = "hi" if "indian" in query or "bollywood" in query else "en"
            
            # Discover endpoint allows language + region filtering
            url = (f"https://api.themoviedb.org/3/discover/movie?api_key={key}"
                   f"&region=IN&with_original_language={lang}&sort_by=primary_release_date.desc")
            
            response = requests.get(url, timeout=(5, 10))
            response.raise_for_status()
            res = response.json()
            movies = res.get('results', [])[:10]
            
            if movies:
                return "\n".join([f"- {m['title']} (Released: {m['release_date']})" for m in movies])
            else:
                raise Exception("No specific nationality results found on TMDB.")

        except Exception as e:
            # --- 2. BACKUP: OMDb (Triggered if TMDB fails or is empty) ---
            try:
                omdb_key = os.environ.get('OMDB_API_KEY')
                # For OMDb, we search for the year 2026 + nationality keyword
                search_term = "Indian 2026" if "indian" in query else "2026"
                
                res = requests.get(f"http://www.omdbapi.com/?s={search_term}&type=movie&apikey={omdb_key}", timeout=5).json()
                search_results = res.get('Search', [])
                
                if search_results:
                    return "Sir, TMDB is unresponsive. OMDb Backup results:\n" + \
                           "\n".join([f"- {m['Title']} ({m['Year']})" for m in search_results[:5]])
                return "All cinematic data streams are currently offline, Sir."
            except:
                return "Emergency: Movie data sector total failure."
              
    # --- NEWS SECTION ---
    elif category == "news":
        # Option 1: NewsData.io (Primary)
        try:
            key = os.environ.get('NEWSDATA_KEY')
            url = f"https://newsdata.io/api/1/news?apikey={key}&q={query}&country=in"
            res = requests.get(url, timeout=10).json()
            # Corrected Indexing: Extract titles from the list
            titles = [art['title'] for art in res.get('results', [])[:5]]
            return "\n".join(titles) if titles else "No headlines found."
        except:
            # Option 2: NewsAPI.org (Backup)
            try:
                key = os.environ.get('NEWSAPI_ORG_KEY')
                res = requests.get(f"https://newsapi.org/v2/everything?q={query}&apiKey={key}", timeout=10).json()
                titles = [art['title'] for art in res.get('articles', [])[:5]]
                return "\n".join(titles)
            except:
                return "News services are currently unavailable."

    # --- COMPANY SEARCH SECTION ---
    elif category == "find_near":
        try:
            # --- STAGE 1: Primary - MapTiler POI ---
            key = os.environ.get('MAPTILER_API_KEY')
            maptiler_url = f"https://api.maptiler.com/geocoding/{query}.json?key={key}&types=poi&proximity=ip"
            
            response = requests.get(maptiler_url, timeout=5)
            res = response.json()
            features = res.get('features', [])
            
            if isinstance(features, list) and len(features) > 0:
                results = [f"🏢 {f.get('text')}\n   📍 {f.get('place_name')}" for f in features[:5]]
                return "\n\n".join(results)
            
            # --- STAGE 2: Backup - LocationIQ ---
            # This triggers if MapTiler returns no businesses
            liq_key = os.environ.get('LOCATION_IQ_KEY')
            if liq_key:
                # Use 'search' endpoint for business queries
                liq_url = f"https://us1.locationiq.com/v1/search?key={liq_key}&q={query}&format=json"
                liq_res = requests.get(liq_url, timeout=5).json()
                
                if isinstance(liq_res, list) and len(liq_res) > 0:
                    results = [f"🏢 {r.get('display_name')}" for r in liq_res[:5]]
                    return "Sir, MapTiler was quiet, but my LocationIQ backup found these:\n\n" + "\n\n".join(results)

            # --- STAGE 3: Final Fallback - Web Search ---
            return f"Sir, I couldn't find registered API markers. Initiating web scan:\n\n{web_search(query)}"

        except Exception as e:
            return f"Mapping sector error: {str(e)}"
        
def generate_mission_pdf(content):
    """BSc Level PDF Generator with Syntax Highlighting for Code Blocks"""
    pdf = FPDF()
    pdf.add_page()
    
    # Split content by markdown code fences
    parts = re.split(r'(```[\s\S]*?```)', content)
    
    for part in parts:
        if part.startswith('```'):
            # --- CODE BLOCK STYLING ---
            # Remove the backticks and language name (e.g., ```python)
            lines = part.split('\n')
            code_text = '\n'.join(lines[1:-1]) 
            
            # Set background to dark gray and text to lime green
            pdf.set_fill_color(30, 30, 30)
            pdf.set_text_color(50, 255, 50) 
            pdf.set_font("courier", 'B', size=9)
            
            # multi_cell with fill=True creates the highlighted box
            pdf.multi_cell(0, 5, txt=code_text, border=0, align='L', fill=True)
            pdf.ln(5)
        else:
            # --- REGULAR TEXT STYLING ---
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("helvetica", size=11)
            pdf.multi_cell(0, 6, txt=part.strip())
            pdf.ln(2)

    filename = f"mission_report_{datetime.now().strftime('%H%M%S')}.pdf"
    pdf.output(filename)
    return filename


def process_eva_command(query):
    global active_mission
    query = query.lower()
    command_handled = False
    global response_text
    response_text = ""

    # --- 1. MOVIE & SHOW LOGIC ---
    if "new movies" in query or "latest movies" in query or "released today" in query:
        # Trigger the 'new_movies' category we built earlier
        data = fetch_external_data("new_movies", "")
        response_text = f"Sir, here are the latest cinematic releases:\n{data}"
        command_handled = True
        return response_text

    # --- 2. NEARBY COMPANIES & LOCATION LOGIC ---
    elif "nearby" in query or "find" in query:
        # Example query: "list website designers in Lucknow"
        search_target = query.replace("nearby", "").replace("find", "").strip()
        # This will now call fetch_external_data with types=poi active
        data = fetch_external_data("find_near", search_target)
        response_text = f"Sector scan complete. Here are the companies I found:\n\n{data}"
        return response_text
    
    # elif "movie" in query or "show" in query:
    #     # Improved extraction: "tell me about the movie inception" -> "inception"
    #     movie_name = query.replace("search movie", "").replace("movie", "").replace("show", "").strip()
    #     if movie_name:
    #         data = fetch_external_data("movies", movie_name)
    #         response_text = f"Found these details: {data}"
    #         command_handled = True
    #         return response_text

    # --- 2. NEWS & CURRENT AFFAIRS LOGIC ---
    elif "news" in query or "current affairs" in query:
        topic = query.replace("latest news about", "").replace("news", "").replace("current affairs", "").strip()
        if not topic: topic = "India" # Default to India if no topic specified
        data = fetch_external_data("news", topic)
        response_text = f"Here is the latest headline: {data}"
        command_handled = True
        return response_text

    # --- 3. MAPS & LOCATION LOGIC ---
    elif "where is" in query or "map of" in query or "location of" in query:
        location = query.replace("where is", "").replace("map of", "").replace("location of", "").strip()
        if location:
            map_url = fetch_external_data("map", location)
            webbrowser.open(map_url)
            response_text = f"Locating {location} on the map for you, Sir."
            command_handled = True
            return response_text

    # --- PROJECT CREATION ---
    if "create new project" in query or "create new directory" in query:
        project_name = query.replace("create new project", "").replace("create new directory", "").strip()
        if project_name:
            active_mission = project_name.replace(" ", "_").lower()
            set_active_project(active_mission) 
            response_text = f"Project '{project_name}' initialized, Sir."
            # We DON'T return here; let it check for other commands
            command_handled = True
            return response_text

    # --- MISSION ROUTING (GO TO) ---
    if "go to" in query and "directory" in query:
        folder_name = query.replace("go to", "").replace("directory", "").strip()
        folder_name = folder_name.replace("eva","").strip()
        active_mission = folder_name.replace(" ", "_").lower()
        set_active_project(active_mission)
        response_text = f"Systems routed to {folder_name} directory, Sir."
        command_handled = True
        return response_text

    # --- MANUAL SAVE TRIGGER ---
    if "save it" in query or "save this convo" in query:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
            if history:
                last_interaction = history[-1]
                # 1. Save the file locally on the Render server
                file_path = archive_groq_response(last_interaction['user'], last_interaction['eva'])
                
                # 2. TRIGGER THE GITHUB PUSH
                sync_success = push_to_github() 
                
                if sync_success:
                    return f"Interaction archived in the {active_mission} sector and synced to GitHub, Sir."
                else:
                    return f"Archived locally, but GitHub sync failed. Check Render logs."
                
    if "generate image" in query or "draw" in query or "image" in query or "img" in query:
        prompt = query.replace("generate image", "").replace("draw", "").replace("image","").replace("img","").strip()
        img_url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?nologo=true"
        return f"Visualizing: {prompt}. Source: {img_url}"
    
    if "create pdf" in query or "save as pdf" in query:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
            
            # USE RAW EVA DATA (not escaped HTML)
            raw_text_to_save = history[-1]['eva'] if history else "No data."
            
            pdf_name = generate_mission_pdf(raw_text_to_save)
            return f"MISSION_PDF_READY:{pdf_name}"      

    # --- ENHANCED SCRAPING TRIGGER ---
    if "scrape" in query or "read the page" in query:
        # Find the URL in the query or use search to find a URL first
        speak("Initializing deep research mode...")
        
        # 1. Use Search to find the best link
        search_query = query.replace("scrape", "").replace("read the page", "").strip()
        search_results = list(DDGS().text(search_query, max_results=1))
        
        if search_results:
            target_url = search_results[0]['href']
            speak(f"Reading documentation from {search_results[0]['title']}...")
            
            # 2. Scrape the full text from that URL
            deep_content = scrape_website_content(target_url)
            
            # 3. Use AI to summarize the deep content
            prompt = f"The user asked: {query}. Here is the full content from the documentation: {deep_content}. Explain this clearly."
            response_text = get_ai_response(prompt)
            return response_text
        # --- WEB SEARCH TRIGGER ---
    # --- UPGRADED WEB SEARCH TRIGGER (Recency Priority) ---
    # --- DYNAMIC WEB SEARCH TRIGGER (Automatic Date Update) ---
    if "search for" in query or "who is" in query or "what is" in query:
        search_query = query.replace("search for", "").replace("who is", "").replace("what is", "").strip()
        
        # 1. DYNAMIC DATE CAPTURE
        # This gets 'February 2026', 'March 2026', etc. automatically
        current_date_context = datetime.now().strftime("%B %Y")
        
        # 2. Get raw search data
        raw_data = web_search(search_query)
        
        # 3. Dynamic Priority Prompt
        prompt = (
            f"User Question: '{search_query}'.\n"
            f"System Context: Today is {current_date_context}.\n"
            f"Live Web Data: {raw_data}.\n\n"
            "CRITICAL: Prioritize information matching the current year/month above. "
            "If the web results mention a name change or update from 2024-2026, "
            f"provide that as the definitive answer, and don't mention {current_date_context} for every chat"
            "when ever website or comapanies is asked than provide data locally as in prompt mention and provide them as list form than also read content."
        )
        
        response_text = get_ai_response(prompt)
        command_handled = True
        return response_text

    
    #dynamic task
    # if "open" in query:
    #     target = query.replace("open", "").strip()
        
    #     # 1. Local App Check
    #     apps = {"notepad": "notepad.exe", "calculator": "calc.exe", "vs code": "code"}
    #     if target in apps:
    #         os.startfile(apps[target])
    #         # Return this so the Flask route speaks it through the phone
    #         return f"Opening {target}, Sir."

    #     # 2. Website Search Logic
    #     # Instead of speak(), we update response_text
    #     try:
    #         with DDGS() as ddgs:
    #             results = list(ddgs.text(f"{target} official website", max_results=1))
    #             if results:
    #                 url = results[0]['href']
    #                 webbrowser.open(url)
    #                 # This entire sentence will now be routed to your phone
    #                 return f"Found the official link. Launching {target} now, Sir."
    #             else:
    #                 return f"I searched the web but couldn't find a live link for {target}."
    #     except Exception as e:
    #         return f"Search encountered an error, Sir."

    # 3. AUTOMATION (Improved Stability)
    # if "screenshot" in query:
    #     try:
    #         pyautogui.screenshot("eva_snap.png")
    #         response_text = "Screenshot captured and saved."
    #     except Exception as e:
    #         response_text = "Sir, I couldn't capture the screen. Check folder permissions."
    #     command_handled = True
    #     return response_text
    
    # if "mute" in query:
    #     pyautogui.press("volumemute")
    #     response_text = "System volume toggled."
    #     command_handled = True

    # # 4. OS TASKS
    # if "lock the system" in query:
    #     response_text = "Locking the workstation."
    #     os.system("shutdown /l")
    #     command_handled = True

    # if "minimize" in query or "go to desktop" in query:
    #     pyautogui.hotkey('win', 'd') #
    #     return "Clearing the workspace, Sir."

    # if "close this" in query or "close window" in query:
    #     pyautogui.hotkey('alt', 'f4') #
    #     return "Terminating active window."
    
    # if "system" in query or "launch" in query or"run" in query:
    #     # 1. LIVE SEARCH: Get the most updated 2026 command first
    #     search_query = f"modern Windows 11 CMD command for {query} 2026"
    #     raw_web_data = web_search(search_query) # This uses your DDGS live search

    #     # 2. AI CLEANUP: Use Groq only to format the live data
    #     prompt = (f"The user wants to: {query}. Based on this 2026 web data: {raw_web_data}, "
    #               "extract ONLY the specific CMD command. Return nothing but the command.")
    #     raw_cmd = get_ai_response(prompt).strip()
        
    #     # 3. SAFETY CHECK: Same as before
    #     critical_cmds = ["shutdown", "restart", "del", "rmdir", "format"]
    #     if any(c in raw_cmd.lower() for c in critical_cmds):
    #         # Remember: This speaks to your phone if in Phone Mode!
    #         speak(f"Sir, that is a critical command: {raw_cmd}. Confirm execution?")
    #         confirm = listen().lower()
    #         if "yes" not in confirm: return "Security abort."

    #     # 4. SECURE EXECUTION: Optimized for Windows 11 Apps & Folders
    #     try:
    #         # Check if raw_cmd is actually a path to one of your project folders
    #         # We check the 'history/ai_responses' sector specifically
    #         potential_path = os.path.join(HISTORY_DIR, raw_cmd)
            
    #         if os.path.isdir(potential_path):
    #             # If it's a folder, we MUST use 'explorer' to open it
    #             subprocess.Popen(f'explorer "{potential_path}"', shell=True)
    #             return f"Opening your {raw_cmd} directory, Sir."
    #         else:
    #             # If it's a standard command like 'taskmgr', run it normally
    #             subprocess.Popen(raw_cmd, shell=True)
    #             return f"Task initiated with verified 2026 data: {raw_cmd}"
                
    #     except Exception as e:
    #         return f"I encountered an error launching that, Sir. Error: {e}"

    # 5. HISTORY REVIEW
    if "show history" in query or "tasks i performed" in query:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
                last_task = history[-1]['user'] if history else "none"
                response_text = f"Your last recorded task was: {last_task}"
                
        else:
            response_text = "No history file found yet."
        command_handled = True
        return response_text
    
    if len(response_text) > 4000:
        # Save the huge data to a file instead of "blasting" it to the screen
        file_path = archive_groq_response("Large Data Request", response_text)
        return f"Response was too large for safe rendering. I have secured the full data in your mission logs: {file_path}"
        

    if "note this" in query or "remind me" in query:
        note_content = query.replace("note this", "").replace("remind me", "").strip()
        
        if note_content:
            success = save_note(note_content)
            if success:
                response_text = f"I've secured that in your notes, Sir: {note_content}"
                
            else:
                response_text = "Sir, I encountered a permission error while saving your note."
        else:
            response_text = "What exactly would you like me to note down, Sir?"
        command_handled = True
        return response_text

    # 6. AI FALLBACK
    # 6. ENHANCED DYNAMIC FALLBACK (The "Always Up-to-Date" Engine)
    if not command_handled:
        # A. Get current time context for the AI
        current_date_context = datetime.now().strftime("%B %Y")
        
        # B. Perform an automatic web search for the unknown query
        print(f"System: No command detected. Initiating default web search for '{query}'...")
        raw_web_data = web_search(query)
        
        # C. Specialized Prompt to prioritize India and 2026 data
        # This matches the system_msg style you shared in your screenshot.
        prompt = (
            f"You are EVA, developed in India by Akash. Current Date: {current_date_context}.\n"
            f"User Question: {query}\n\n"
            f"Live Web Research: {raw_web_data}\n\n"
            "INSTRUCTION: Prioritize official latest information, searches, links, current affairs, news, name changes or facts after 2024 to since today "
            "If the question is about India, ensure the response is 100% accurate as of today. and don't mention month in every conversation and if about movies or movie list asked than provide recent data to them."
            "whenever nearby comapnies or website is asked than provide data according to local as prompt said."
        )
        
        response_text = get_ai_response(prompt)
        return response_text


# --- FLASK ROUTES ---
# State management
io_config = {"mic": "Backend", "speaker": "Backend"}

@app.route('/update-io', methods=['POST'])
def update_io():
    global io_config
    io_config.update(request.get_json())
    return jsonify({"status": "success", "config": io_config})

@app.route('/list-directories', methods=['GET'])
def list_directories():
    try:
        # Scans your history folder for project directories
        dirs = [d for d in os.listdir(HISTORY_DIR) if os.path.isdir(os.path.join(HISTORY_DIR, d))]
        return jsonify({"directories": dirs})
    except Exception as e:
        return jsonify({"directories": [], "error": str(e)})
    

@app.route('/switch-workspace', methods=['POST']) # Ensure 'POST' is in the methods list
def switch_workspace():
    global active_mission
    try:
        data = request.get_json()
        new_folder = data.get("directory")
        
        if new_folder:
            # Update the global mission context
            active_mission = new_folder.replace(" ", "_").lower()
            
            # Ensure the directory physically exists
            project_path = set_active_project(active_mission)
            
            print(f"System: Switched to workspace -> {active_mission}")
            return jsonify({
                "status": "success", 
                "message": f"Workspace switched to {active_mission}",
                "active": active_mission
            })
    except Exception as e:
        print(f"Workspace Switch Error: {e}")
        
    return jsonify({"status": "error", "message": "Invalid request"}), 400
@app.route('/get-mission-logs', methods=['GET'])
def get_mission_logs():
    global active_mission
    mission_path = os.path.join(HISTORY_DIR, active_mission)
    
    if not os.path.exists(mission_path):
        return jsonify({"logs": []})
        
    try:
        files = [f for f in os.listdir(mission_path) if os.path.isfile(os.path.join(mission_path, f))]
        # Sort by newest first
        files.sort(key=lambda x: os.path.getmtime(os.path.join(mission_path, x)), reverse=True)
        
        log_data = []
        for file_name in files[:10]: 
            try:
                # Use 'errors="ignore"' to handle files with weird characters
                with open(os.path.join(mission_path, file_name), "r", encoding="utf-8", errors="ignore") as f:
                    log_data.append({
                        "name": file_name,
                        "content": f.read(2000) 
                    })
            except Exception as file_err:
                print(f"Skipping file {file_name} due to error: {file_err}")
                continue # Keep going even if one file fails
                
        return jsonify({"logs": log_data})
    except Exception as e:
        print(f"Major log retrieval error: {e}")
        return jsonify({"logs": [], "error": str(e)}), 200 # Return 200 to stop the UI from breaking
    
@app.route('/read-file', methods=['GET'])
def read_file():
    global active_mission
    file_name = request.args.get('name')
    file_path = os.path.join(HISTORY_DIR, active_mission, file_name)
    
    try:
        # Using 'errors="ignore"' to keep the system stable
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"content": f"Error reading file: {str(e)}"}), 500


@app.route('/run-eva', methods=['POST'])
def run_eva():
    data = request.get_json(silent=True) or {}
    image_data = data.get("image_data")
    user_query = data.get("transcript", "").strip()
    
    response_text = ""

    # --- 1. PRIORITY: IMAGE ANALYSIS ---
    # If an image is present, we ignore the mic and process the visual data
    if image_data:
        prompt = user_query if user_query else "Describe this image in detail."
        try:
            # Note: Ensure analyze_image_qa handles the base64 string correctly
            response_text = analyze_image_qa(image_data, prompt)
            response_text = f"[Visual Analysis] {response_text}"
        except Exception as e:
            response_text = f"Visual Core Error: {str(e)}"

    # --- 2. SECONDARY: TEXT COMMANDS ---
    elif user_query:
        # Check if the user is trying to use the backend mic while on Render
        if io_config["mic"] == "Backend" and os.environ.get("RENDER"):
            return jsonify({
                "response": "Sir, I cannot access your laptop mic from the cloud. Please use Text Input or Phone Mic.",
                "audio": "frontend"
            })
        
        # If it's a normal text command or a local mic command
        response_text = process_eva_command(user_query)

    # --- 3. FALLBACK: NO DATA ---
    else:
        return jsonify({"response": "I am standing by, Sir. Please provide a command or an image."})

    # --- 4. FINAL RENDERING ---
    safe_response = html.escape(response_text)
    log_task(user_query or "[Visual Scan]", response_text) 
    
    return jsonify({
        "transcript": user_query or "[Image Uploaded]", 
        "response": safe_response,
        "audio": "frontend" if io_config["speaker"] == "Frontend" else "backend"
    })

from flask import send_file

@app.route('/download/<filename>')
def download_file(filename):
    try:
        # This sends the actual PDF file to your browser
        return send_file(filename, as_attachment=True)
    except Exception as e:
        return f"Error: File not found or deleted by Render. {e}"
@app.route('/')
def index():
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except Exception:
        return "Error: index.html not found, Sir."

@app.route('/run-eva', methods=['POST'])

@app.route('/run-shortcut', methods=['POST'])
def run_shortcut():
    data = request.get_json()
    command = data.get("command")
    if command:
        response_text = process_eva_command(command)
        log_task(command, response_text) # Ensure it still logs!

        # --- HIGHLIGHTED FIX: ADD SPEAKER CHECK HERE ---
        if io_config["speaker"] == "Backend":
            speak(response_text) # Laptop speaks
            return jsonify({"transcript": "Shortcut", "response": response_text, "audio": "backend"})
        else:
            return jsonify({"transcript": "Shortcut", "response": response_text, "audio": "frontend"})
            
    return jsonify({"response": "No command received."})

@app.route('/stop-eva', methods=['POST'])
def stop_eva():
    # try:
    #     # We initialize a quick engine and tell it to stop any active loops
    #     stop_engine = pyttsx3.init()
    #     stop_engine.stop()
    #     print("EVA: Speech interrupted by User.")
    #     return jsonify({"status": "stopped", "response": "Speech stopped, Sir."})
    # except Exception as e:
    #     return jsonify({"status": "error", "message": str(e)})
    print("EVA: System Silenced by User.")
    return jsonify({"status": "stopped", "response": "System Silenced, Sir."})
# Default mood
current_mood = "Professional" 

@app.route('/set-mood', methods=['POST'])
def set_mood():
    global current_mood
    data = request.get_json()
    new_mood = data.get("mood")
    if new_mood:
        current_mood = new_mood
        speak(f"Mood updated to {current_mood} mode, Sir.")
        return jsonify({"status": "success", "mood": current_mood})
    return jsonify({"status": "error"}), 400

@app.after_request
def add_header(response):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 0 seconds.
    """
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

def startup_greeting():
    hour = datetime.now().hour
    greeting = "Good Morning" if hour < 12 else "Good Afternoon" if hour < 18 else "Good Evening"
    speak(f"{greeting} Sir. Systems are nominal. EVA is online.")

if __name__ == "__main__":
    try:
        repo = git.Repo(BASE_DIR)
        
        # FIX: Check if 'origin' exists in remotes before accessing it
        if 'origin' in repo.remotes:
            origin = repo.remotes['origin'] # Access via key rather than attribute
            origin.pull('main')
            print("System: Project history restored from GitHub.")
        else:
            print("System: 'origin' remote not found. Skipping startup sync.")
            
    except Exception as e:
        # This is where your current error is being caught
        print(f"System: Startup sync bypass: {e}")

    startup_greeting()
    port = int(os.environ.get("PORT", 10000))
    serve(app, host='0.0.0.0', port=port)