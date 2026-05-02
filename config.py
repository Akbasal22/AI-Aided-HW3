DB_PATH = "wiki_rag.db"
CHROMA_DIR = "./chroma_store"

CHUNK_SIZE_WORDS = 2000
CHUNK_OVERLAP_WORDS = 200

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CLASSIFIER_LLM = "gemma3:1b"
LLM_MODEL = "llama3.2:3b"
OLLAMA_BASE_URL = "http://localhost:11434"

PEOPLE_COLLECTION = "people_store"
PLACES_COLLECTION = "places_store"

TOP_K = 3

PEOPLE_TITLES = [
    "Albert Einstein",
    "Marie Curie",
    "Leonardo da Vinci",
    "William Shakespeare",
    "Ada Lovelace",
    "Nikola Tesla",
    "Lionel Messi",
    "Cristiano Ronaldo",
    "Taylor Swift",
    "Frida Kahlo",
    "Isaac Newton",
    "Charles Darwin",
    "Cleopatra",
    "Napoleon Bonaparte",
    "Mahatma Gandhi",
    "Nelson Mandela",
    "Stephen Hawking",
    "Elon Musk",
    "Aristotle",
    "Wolfgang Amadeus Mozart",
    "Adolf Hitler"
]

PLACES_TITLES = [
    "Eiffel Tower",
    "Great Wall of China",
    "Taj Mahal",
    "Grand Canyon",
    "Machu Picchu",
    "Colosseum",
    "Hagia Sophia",
    "Statue of Liberty",
    "Pyramids of Giza",
    "Mount Everest",
    "Stonehenge",
    "Acropolis of Athens",
    "Angkor Wat",
    "Chichen Itza",
    "Petra",
    "Sagrada Familia",
    "Big Ben",
    "Sydney Opera House",
    "Amazon River",
    "Niagara Falls",
]
