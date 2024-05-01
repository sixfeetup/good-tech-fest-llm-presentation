import json
import os
import subprocess

import chromadb

from constants import DEBUG, EMBEDDING_MODEL, VECTOR_STORE_PATH


def get_local_credentials():
    keypath = subprocess.check_output(
        ".venv/bin/llm keys path".split(), text=True
    ).strip()
    if DEBUG:
        print(keypath)
    with open(keypath) as f:
        return json.load(f)["openai"]


def initialize_vector_store(collection_name, reset_vector_store=False):
    os.environ["OPENAI_API_KEY"] = os.environ.get(
        "OPENAI_API_KEY", get_local_credentials()
    )

    embedding_function = chromadb.utils.embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name=EMBEDDING_MODEL,
    )
    chroma_client = chromadb.PersistentClient(
        path=VECTOR_STORE_PATH,
        settings=chromadb.Settings(
            allow_reset=reset_vector_store,
            anonymized_telemetry=False,
        )
    )
    if reset_vector_store:
        print("RESETTING VECTOR STORE.")
        chroma_client.reset()
    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_function,
    )
    return collection

