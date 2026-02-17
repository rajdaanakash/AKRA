API_KEY = "AIzaSyDlbu6ZjJzvmWWAHQde8iWumTyAKPsn48w"
# import google.generativeai as genai
# --- CONFIGURATION ---
 
# genai.configure(api_key=API_KEY)
# model = genai.GenerativeModel(model_name="gemini-2.0-flash")

# def get_eva_response(user_input):
#     # This is the "System Prompt" that gives her the JARVIS/EVA personality
#     system_instruction = (
#         "You are EVA (Enhanced Virtual Architect), a highly intelligent, witty, "
#         "and sophisticated AI assistant. You serve Akash, a Computer Science student. "
#         "Your tone is helpful but slightly sassy, like JARVIS. Keep responses concise."
#     )
#     full_prompt = f"{system_instruction}\nUser: {user_input}\nEVA:"
    
#     response = model.generate_content(full_prompt)
#     return response.text

        # # Send to Gemini Brain
        # eva_reply = get_eva_response(query)
        # speak(eva_reply)