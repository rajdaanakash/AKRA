import speech_recognition as sr
import pyttsx3
import datetime
import webbrowser
import os


# Initialize Voice Engine
engine = pyttsx3.init()
voices = engine.getProperty('voices')
# Change index to 1 for female voice (EVA) or 0 for male
engine.setProperty('voice', voices[1].id) 
engine.setProperty('rate', 185) # Speed

def speak(text):
    print(f"EVA: {text}")
    engine.say(text)
    engine.runAndWait()

def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening for Sir...")
        r.pause_threshold = 0.8
        audio = r.listen(source)
    try:
        print("Processing...")
        query = r.recognize_google(audio, language='en-in')
        print(f"User: {query}")
        return query
    except Exception:
        return ""



# --- MAIN EXECUTION ---
if __name__ == "__main__":
    hour = int(datetime.datetime.now().hour)
    greeting = "Good Morning" if hour < 12 else "Good Afternoon" if hour < 18 else "Good Evening"
    
    speak(f"{greeting} Sir. Systems are nominal. EVA is online and ready for your command.")

    while True:
        query = listen().lower()

        # Store all your links here
        websites = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "instagram": "https://www.instagram.com/",
            "github": "https://github.com",
            "gemini": "https://gemini.google.com/app"
        }

        # The logic to handle the query
        for site in websites:
            if f"open {site}" in query:
                speak(f"Opening {site}")
                webbrowser.open(websites[site])
        
            


        if "go to sleep" in query:
            speak("Understood, Sir. Powering down. Have a productive evening.")
            break

        # Add this below your websites dictionary
        apps = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "task manager": "taskmgr.exe",
            "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "spotify": "C:\\Users\\Lenovo\\Desktop\\Spotify.lnk",
            "discord": "C:\\Users\\Lenovo\\Desktop\\Discord.lnk",
            "vs code": "C:\\Users\\Lenovo\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Visual Studio Code\\Visual Studio Code.lnk"
        }

        # Logic to handle opening OS apps
        for app in apps:
            if f"open {app}" in query:
                speak(f"Opening {app}, Sir.")
                try:
                    os.startfile(apps[app])
                except Exception as e:
                    speak(f"I'm sorry, I couldn't find the path for {app}.")
                break

        
        # task for operating sytems
        ostask = {
            "shutdown": "shutdown /s /t 0",
            "lock": "shutdown /l",
            "restart": "shutdown /r /t 0",
            "hibernate": "shutdown /h"
        }

        for task in ostask:
            if f"{task} the laptop" in query:
                speak(f"{task}ing the laptop, Sir.")
                try:
                    os.system(ostask[task])
                except Exception as e:
                    speak(f"I'm sorry, I couldn't find the path for {task}.")
                break
        if "play" in query:
            song = query.replace("play", "")
            speak(f"Playing {song} on YouTube.")
            # This opens the default browser to a YouTube search
            os.system(f"start https://www.youtube.com/results?search_query={song.replace(' ', '+')}")


