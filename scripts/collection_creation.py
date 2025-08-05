import os
import time
import pymupdf4llm
from qdrant_client import QdrantClient, models
from llama_index.core import (
    Document,
    VectorStoreIndex,
    StorageContext,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from google.genai.types import EmbedContentConfig
from typing import List
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
QDRANT_URL = os.environ["QDRANT_URL"]
QDRANT_API_KEY = os.environ["QDRANT_API_KEY"]

DATA_DIR = "data"
COLLECTION_NAME = "Animal_Habitat_Conservation_Project"
EMBED_MODEL = "text-embedding-004"
EMBEDDING_DIM = 768

class RateLimitedGoogleGenAIEmbedding(GoogleGenAIEmbedding):
    """Custom embedding class that adds delays to respect API rate limits."""
    
    def __init__(self, delay_seconds: float = 2.0, **kwargs):
        super().__init__(**kwargs)
        # Store delay as a private attribute to avoid Pydantic validation issues
        self._delay_seconds = delay_seconds
        
    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Override to add delay between API calls."""
        print(f"Processing batch of {len(texts)} texts with {self._delay_seconds}s delay...")
        
        # Add delay before making the API call
        time.sleep(self._delay_seconds)
        
        # Call the parent method
        return super()._get_text_embeddings(texts)

def load_and_parse_pdfs(directory: str) -> list[Document]:
    """Loads and parses all PDF files from a specified directory."""
    documents = []
    print(f"Loading PDFs from '{directory}'...")
    for filename in os.listdir(directory):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(directory, filename)
            try:
                # Extract text in Markdown format for better structure
                md_text = pymupdf4llm.to_markdown(pdf_path, write_images=False)
                doc = Document(text=md_text, metadata={"file_name": filename})
                documents.append(doc)
            except Exception as e:
                print(f"Skipping file {filename} due to error: {e}")
    print(f"Successfully processed {len(documents)} PDF documents.")
    return documents

def main():
    """
    Main execution function to set up the RAG pipeline:
    1. Loads PDF documents.
    2. Initializes embedding with rate limiting.
    3. Sets up a Qdrant vector collection.
    4. Creates and stores document embeddings in the collection.
    """
    if not all([GOOGLE_API_KEY, QDRANT_URL, QDRANT_API_KEY]):
        print("Error: Required environment variables (GOOGLE_API_KEY, QDRANT_URL, QDRANT_API_KEY) are not set.")
        return

    # Check for data directory
    if not os.path.exists(DATA_DIR) or not os.listdir(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"Error: The '{DATA_DIR}' directory is empty.")
        print("Please add your PDF files to this directory and run the script again.")
        return

    # Initialize models with rate limiting
    embed_model = RateLimitedGoogleGenAIEmbedding(
        model_name=EMBED_MODEL,
        delay_seconds=1.0,
        config=EmbedContentConfig(
            task_type="retrieval_document",
            output_dimensionality=EMBEDDING_DIM
        )
    )

    # Initialize Qdrant client
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # Create collection if it doesn't exist
    if not client.collection_exists(collection_name=COLLECTION_NAME):
        print(f"Creating Qdrant collection: '{COLLECTION_NAME}'")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=EMBEDDING_DIM,
                distance=models.Distance.COSINE,
            ),
        )
    else:
        print(f"Collection '{COLLECTION_NAME}' already exists.")

    # Load documents and create vector store
    documents = load_and_parse_pdfs(DATA_DIR)
    if not documents:
        print("No documents were successfully loaded. Exiting.")
        return

    vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION_NAME)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    # Define a chunking strategy to avoid overloading the embedding model.
    node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=20)

    # Create the index, which automatically embeds and stores the documents
    print("Indexing documents... This will take some time due to rate limiting.")
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
        node_parser=node_parser,
        show_progress=True,
    )
    print("Indexing complete.")

if __name__ == "__main__":
    main()