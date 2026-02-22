import os
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# Path to your BSc CS textbooks
KNOWLEDGE_DIR = "./knowledge_base"
DB_DIR = "./eva_brain_db"

# 1. Initialize Embeddings (Using a free local model to save tokens/cost)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def update_knowledge_base():
    """Reads PDFs, chunks them, and saves to local Vector DB."""
    if not os.path.exists(KNOWLEDGE_DIR):
        os.makedirs(KNOWLEDGE_DIR)
        return "Sir, please add PDFs to the knowledge_base folder."

    # Load all PDFs from your textbooks folder
    loader = DirectoryLoader(KNOWLEDGE_DIR, glob="./**/*.pdf", loader_cls=PyPDFLoader)
    documents = loader.load()

    # --- SMART CHUNKING ---
    # We split into 1000 chars with overlap to keep context safe
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = text_splitter.split_documents(documents)

    # Create/Update the Vector Database on your Lenovo LOQ
    vectorstore = Chroma.from_documents(
        documents=chunks, 
        embedding=embeddings, 
        persist_directory=DB_DIR
    )
    # Ensure all data is physically written to the E: driv
    vectorstore.persist()
    return f"Success: {len(chunks)} knowledge chunks indexed, Sir."

def get_relevant_context(query):
    """Retrieves only the top 3 most relevant chunks to stay under token limits."""
    if not os.path.exists(DB_DIR):
        return ""
    
    db = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    # 'k=3' ensures we never exceed the Groq context window
    docs = db.similarity_search(query, k=3)
    
    context = "\n".join([doc.page_content for doc in docs])
    return context