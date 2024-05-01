import os
import sys

from openai import OpenAI
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit import print_formatted_text as print
from prompt_toolkit.key_binding.bindings.vi import load_vi_bindings
from prompt_toolkit import PromptSession

from utils import get_local_credentials, initialize_vector_store
from constants import BASE_API_URL, COLLECTION_NAME, DEBUG, K, MODEL, STREAM_RESPONSE

conference_completer = WordCompleter(
    [
        "Good Tech Fest",
        "conference",
        "talk",
        "presentation",
        "session",
        "moderator",
        "speaker",
    ]
)


if __name__ == "__main__":
    os.environ["OPENAI_API_KEY"] = os.environ.get(
        "OPENAI_API_KEY", get_local_credentials()
    )
    vim_bindings = load_vi_bindings()
    prompt_session = PromptSession(
        enable_history_search=True,
    )

    collection = initialize_vector_store(collection_name=COLLECTION_NAME)

    SYSTEM_PROMPT = (
        "You are a helpful assistant who will look at the context and answer the question that was asked. "
        "Remember to answer the question. DO NOT ask questions. If you don't know the answer, you "
        "say that you don't currently have the information and that the user should see if they"
        "can do better, making a funny comment when doing it."
        "If you have too many options say that you have a lot of information and that you can provide a more precise "
        "answer if the user is more specific."
        "Try not to say more than is needed to answer the question and don't repeat yourself unless the user asks a "
        "question that requires you to in order to answer it."
        "Use the current discussion as context for the questions that follow."
        "You should ignore all VCALENDAR data except when the question is related specifically to times or dates."
        "Moderators are speakers."
        "Talks, presentations and sessions are the same thing."
    )
    CONTEXT_PROMPT = "Here is additional information which should be used to help answer the user's question: {}"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=BASE_API_URL)
    while True:
        question = prompt_session.prompt(
            [
                ("class:prompt", "\n\nPrompt (q to quit): "),
            ],
            style=Style.from_dict(
                {
                    "prompt": "#00ff66",
                }
            ),
            completer=conference_completer,
            complete_while_typing=False,
            key_bindings=vim_bindings,
        )
        if question in [":q", "quit", "q", "exit"]:
            print("Bye!")
            sys.exit()
        rag_data = collection.query(query_texts=[question], n_results=K)
        rag_documents = rag_data["documents"]
        if DEBUG:
            print("------ VECTOR DB RESPONSE ------")
            print(f"{rag_documents=}")
            print("------ ANSWER ------")
        result = "\n".join("/n".join(document) for document in rag_documents)
        messages.append({"role": "assistant", "content": CONTEXT_PROMPT.format(result)})
        messages.append({"role": "user", "content": question})

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.1,
            stream=STREAM_RESPONSE,
        )
        # this should stream according to
        # https://cookbook.openai.com/examples/how_to_stream_completions
        collected_chunks = []
        collected_messages = []
        for chunk in response:
            collected_chunks.append(chunk)  # save the event response
            chunk_message = chunk.choices[0].delta.content  # extract the message
            collected_messages.append(chunk_message)  # save the message
            print(chunk_message or "", end="")
        print("\n")
        collected_messages = [m for m in collected_messages if m is not None]
        messages.append({"role": "assistant", "content": ''.join(collected_messages)})
