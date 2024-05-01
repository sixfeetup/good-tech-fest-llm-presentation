import os

COLLECTION_NAME = "presentation"
EMBEDDING_MODEL = "text-embedding-3-small"
K = 3
# HOST = "ollama"
HOST = "openai"
if HOST == "openai":
    BASE_API_URL = "https://api.openai.com/v1"
    # MODEL = "gpt-3.5-turbo-16k" # use this for early testing, cheaper, but noticeably worse
    MODEL = "gpt-4-turbo"
elif HOST == "ollama":
    BASE_API_URL = "http://127.0.0.1:11434/v1"
    MODEL = "llama3"

STREAM_RESPONSE = True
WEBSITE = "www.goodtechfest.com"
PROXYCURL_API_KEY = ""
NUBELA_REQUESTS_PER_MINUTE = 2

DATA_DIR = "data"
VECTOR_STORE_PATH = "persist"
TEMPLATED_DATA_STORE_PATH = os.sep.join([os.getcwd(), DATA_DIR, "templated_data"])
SPEAKER_IMAGE_CACHE_FILE_NAME = os.sep.join([os.getcwd(), DATA_DIR, "image_speakers.json"])

RESET_LINKEDIN_DATA = False
DEBUG = False

RESET_VECTOR_STORE = False
PULL_LINKEDIN = True

