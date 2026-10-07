import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("Error: Please set GEMINI_API_KEY in your .env file!")
    exit(1)

client = genai.Client(api_key=api_key)

chat = client.chats.create(model="gemini-3.5-flash-lite")
response = chat.send_message("Explain me about adhd .")

print(response.text)