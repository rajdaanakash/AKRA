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
import rag_engine

# --- CONFIGURATION ---


API_KEYS = [
    os.environ.get("GROQ_API_KEY_1"),
    os.environ.get("GROQ_API_KEY_2")
]
# Keep only keys that actually exist
API_KEYS = [k for k in API_KEYS if k]
current_key_index = 0

def get_ai_response(prompt):
    global current_key_index
    
    # --- NEW: RETRIEVE TEXTBOOK CONTEXT ---
    # This searches your 6,632 chunks on your E: drive
    local_context = rag_engine.get_relevant_context(prompt)
    
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

    # --- UPDATED SYSTEM MSG WITH RAG ---
    # If context is found, we force EVA to use it
    if local_context:
        system_msg = f"You are EVA, created by Akash. Use this textbook context: {local_context}. Notes:\n{permanent_notes}\nChat:\n{history_context}"
    else:
        system_msg = f"You are EVA, created by Akash. Notes:\n{permanent_notes}\nChat:\n{history_context}"

    # --- 2. THE ROTATION LOOP ---
    for _ in range(len(API_KEYS)):
        try:
            # Re-initialize client with the current working key
            client = Groq(api_key=API_KEYS[current_key_index])
            
            # This is the block that was showing red lines
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
            )
            return chat_completion.choices[0].message.content

        except Exception as e:
            # Catching the 429 limit you hit earlier
            if "429" in str(e) or "rate_limit" in str(e).lower():
                print(f"System: Key {current_key_index} exhausted. Rotating...")
                current_key_index = (current_key_index + 1) % len(API_KEYS)
                continue 
            else:
                return f"Neural Error: {e}"
                
   

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
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # --- AI-POWERED DETECTION ---
        # Look for the markdown code block: ```language
        match = re.search(r"```(\w+)\n(.*?)\n```", response, re.DOTALL)
        
        if match:
            # The AI has already identified the language here (e.g., 'python', 'html')
            detected_lang = match.group(1).lower()
            save_data = match.group(2)
            
            # Map common names to extensions, but keep it flexible
            ext_map = {"python": ".py", "javascript": ".js", "typescript": ".ts", "markdown": ".md"}
            # If it's a known shorthand (like 'js'), use it; otherwise, use .[detected_lang]
            ext = ext_map.get(detected_lang, f".{detected_lang}")
        else:
            ext = ".txt"
            save_data = response

        filename = f"{query[:20].replace(' ', '_')}_{timestamp}{ext}"
        file_path = os.path.join(mission_path, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(save_data)
            
        print(f"File created: {file_path}")
        push_to_github() # Your verified sync fix
        return file_path
    except Exception as e:
        print(f"Archive Error: {e}")
        return None
    
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
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.pause_threshold = 0.8
        audio = r.listen(source)
    try:
        query = r.recognize_google(audio, language='en-in')
        print(f"User: {query}")
        return query
    except Exception:
        return ""


def set_active_project(name):
    """Creates a new folder for the current project in the history directory."""
    global HISTORY_DIR #
    # Path: history/ai_responses/your_project_name
    project_path = os.path.join(HISTORY_DIR, name) 
    
    if not os.path.exists(project_path):
        os.makedirs(project_path) #
        print(f"System: Created new directory at {project_path}")
    
    return project_path

def process_eva_command(query):
    global active_mission # Use only this one global
    query = query.lower()
    command_handled = False
    global response_text
    response_text = ""

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
    if "search for" in query or "who is" in query or "what is" in query:
        search_query = query
        
        raw_data = web_search(search_query)
        prompt = (f"The user asked: '{search_query}'. Here is live data from the web: {raw_data}. "
          "If the data contains irrelevant information (like unit converters or ads), "
          "ignore it and only provide a clear biography or answer to the user's question.")
        response_text = get_ai_response(prompt)
        
        # --- HIGHLIGHTED FIX: ADD THIS LINE TO ARCHIVE THE SEARCH ---
        # archive_groq_response(query, response_text) # This creates the .txt file!
        
        command_handled = True
        return response_text

    
    #dynamic task
    if "open" in query:
        target = query.replace("open", "").strip()
        
        # 1. Local App Check
        apps = {"notepad": "notepad.exe", "calculator": "calc.exe", "vs code": "code"}
        if target in apps:
            os.startfile(apps[target])
            # Return this so the Flask route speaks it through the phone
            return f"Opening {target}, Sir."

        # 2. Website Search Logic
        # Instead of speak(), we update response_text
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(f"{target} official website", max_results=1))
                if results:
                    url = results[0]['href']
                    webbrowser.open(url)
                    # This entire sentence will now be routed to your phone
                    return f"Found the official link. Launching {target} now, Sir."
                else:
                    return f"I searched the web but couldn't find a live link for {target}."
        except Exception as e:
            return f"Search encountered an error, Sir."

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
    
    # --- NEW: WEB SEARCH TRIGGER ---
    if "search for" in query or "who is" in query or "what is" in query:
        search_query = query.replace("search for", "").replace("who is", "").replace("what is", "").strip()
        speak(f"Searching the web for {search_query}...")
        
        # 1. Get raw data from the internet
        raw_data = web_search(search_query)
        
        # 2. Feed that data to Groq to get a human-like summary
        prompt = f"The user asked about '{search_query}'. Here is live data from the web: {raw_data}. Summarize this for the user."
        response_text = get_ai_response(prompt)
        command_handled = True

    # 6. AI FALLBACK
    if not command_handled:
        response_text = get_ai_response(query)
        # --- HIGHLIGHTED CHANGE: REMOVED AUTO-ARCHIVE ---
        # We no longer call archive_groq_response here so it stays clean.
        return response_text


# --- FLASK ROUTES ---
# State management
io_config = {"mic": "Backend", "speaker": "Backend"}

@app.route('/update-io', methods=['POST'])
def update_io():
    global io_config
    io_config.update(request.get_json())
    return jsonify({"status": "success", "config": io_config})


@app.route('/run-eva', methods=['POST'])
def run_eva():
    data = request.get_json(silent=True) or {}
    
    if io_config["mic"] == "Backend":
        query = listen()
    else:
        query = data.get("transcript", "")

    if query:
        response_text = process_eva_command(query)
        # Manually log the task here since we removed it from the function
        log_task(query, response_text) 
        
        if io_config["speaker"] == "Backend":
            speak(response_text) # ONLY the laptop speaks
            return jsonify({"transcript": query, "response": response_text, "audio": "backend"})
        else:
            # Laptop stays silent; only the phone will speak
            return jsonify({"transcript": query, "response": response_text, "audio": "frontend"})
            
    return jsonify({"response": "Silence."})

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
    startup_greeting()
    
    # Render will automatically give EVA a port number via an 'Environment Variable'
    # If it can't find one, it will use your default 59059
    port = int(os.environ.get("PORT", 10000))
    
    print(f"EVA is now live on the cloud, Sir. Listening on port {port}...")
    
    # This 'serve' function from Waitress is for Production use
    serve(app, host='0.0.0.0', port=port)