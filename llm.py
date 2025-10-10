import dotenv
from langchain_groq import ChatGroq

dotenv.load_dotenv()

llm = ChatGroq(model="llama-3.1-8b-instant")
