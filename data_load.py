import base64
import hashlib
import json
import os
from json import JSONDecodeError
from pathlib import Path
from time import sleep
from jinja2 import Environment, select_autoescape, FileSystemLoader
from slugify import slugify
import requests
from unstructured.documents.html import HTMLDocument

from constants import (
    WEBSITE, DATA_DIR, COLLECTION_NAME, RESET_VECTOR_STORE, RESET_LINKEDIN_DATA, PROXYCURL_API_KEY,
    SPEAKER_IMAGE_CACHE_FILE_NAME, PULL_LINKEDIN, TEMPLATED_DATA_STORE_PATH, NUBELA_REQUESTS_PER_MINUTE
)
from bs4 import BeautifulSoup
from utils import initialize_vector_store

env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape()
)
if not os.path.exists(SPEAKER_IMAGE_CACHE_FILE_NAME):
    json.dump({}, open(SPEAKER_IMAGE_CACHE_FILE_NAME, "w"))


def get_image_speakers(image_uri):
    """
    This is caching for the name extraction from the image data so we don't hit the
    openai for expensive requests when the signature of the data hasn't changed
    """
    speaker_image_cache = json.load(open(SPEAKER_IMAGE_CACHE_FILE_NAME, "r"))

    image_data, base64_image = get_image_data(image_uri)
    image_data_sig = hashlib.md5(image_data).hexdigest()

    if image_data_sig in speaker_image_cache:
        return speaker_image_cache[image_data_sig]
    speaker_names = extract_names_from_image(base64_image=base64_image)
    speaker_image_cache[image_data_sig] = speaker_names

    json.dump(speaker_image_cache, open(SPEAKER_IMAGE_CACHE_FILE_NAME, "w"))
    return speaker_names


def get_image_data(image_url):
    response = requests.get(image_url)
    base64_image = (
            "data:" + response.headers['Content-Type'] + ";" +
            "base64," + base64.b64encode(response.content).decode("utf-8")
    )
    return response.content, base64_image


def extract_names_from_image(base64_image):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
    }
    payload = {
        "model": "gpt-4-vision-preview",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What are the names in this image? Names are usually given the largest fonts. "
                                "Return only the names in comma separated format without explanation. "
                                "There's no need to warn about not being able to access other information, you are only"
                                "going to be asked for the name."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload
    )
    response_json = response.json()
    speakers = response_json["choices"][0]["message"]["content"]
    return speakers


def populate_data_from_website(collection):
    for root, dirs, files in os.walk(os.sep.join([os.getcwd(), DATA_DIR, WEBSITE])):
        for file_name in files:
            full_file_name = os.path.join(root, file_name)
            # here we want to handle special cases to ensure high quality data
            if file_name in SPESHUL_CASES:
                SPESHUL_CASES[file_name](collection, full_file_name)

            # we also keep the less than high quality data
            doc = HTMLDocument.from_file(full_file_name)
            for i in range(len(doc.pages)):
                print(f"Adding page number {i} from {file_name}")
                collection.upsert(
                    documents=[str(doc.pages[i])],
                    metadatas=[{"file": file_name, "page": i, "Type": "Generic"}],
                    ids=[f"{file_name}_page_{i}"],
                )


def handle_tracks(collection, full_file_name):
    soup = BeautifulSoup(open(full_file_name), "html.parser")
    track_items_list = soup.find_all("article")

    for item in track_items_list:
        track_event_data = structure_track_event_for_template(item)
        # render data to text
        template = env.get_template("track_event.jinja2")
        track_event_content = template.render(track_event=track_event_data)
        print(f"Adding track event speakers {track_event_data['event_speakers_names']}")
        # save template output file for review
        track_event_file = Path(TEMPLATED_DATA_STORE_PATH, "track_event", f"{slugify(track_event_data['event_title'])}_{track_event_data['event_date']}.txt")

        track_event_file.parent.mkdir(exist_ok=True, parents=True)
        with open(track_event_file, "w") as f:
            f.write(track_event_content)
        collection.upsert(
            documents=[track_event_content],
            metadatas=[{
                "Track event name": track_event_data["event_title"],
                "Track event speakers": track_event_data["event_speakers_names"],
                "Type": "Track Event",
                "source": track_event_file.as_posix().replace(os.getcwd(), ""),
            }],
            ids=[f"{slugify(track_event_data['event_title'])}_{track_event_data['event_date']}_track_event"],
        )


def structure_track_event_for_template(track_item):
    track_event_data = {}
    # get the speaker image for parsing
    speakers_img_wrapper = track_item.find('a', attrs={"class": "eventlist-column-thumbnail"})
    speakers_img_uri = speakers_img_wrapper.find("img")
    speakers = get_image_speakers(speakers_img_uri["src"])
    track_event_data["event_speakers_names"] = speakers
    # get the event title
    event_title = track_item.find('a', attrs={"class": "eventlist-title-link"}).contents[0]
    track_event_data["event_title"] = event_title
    # get the event date
    event_date = track_item.find('time', attrs={"class": "event-date"}).contents[0]
    track_event_data["event_date"] = event_date
    # get the event start time
    event_start_time = track_item.find('time', attrs={"class": "event-time-localized-start"}).contents[0]
    track_event_data["event_start_time"] = event_start_time
    # get the event end time
    event_end_time = track_item.find('time', attrs={"class": "event-time-localized-end"}).contents[0]
    track_event_data["event_end_time"] = event_end_time
    # get the event description
    event_description = track_item.find("div", attrs={"class": "eventlist-excerpt"}).text
    track_event_data["description"] = event_description
    return track_event_data


def handle_good_tech_fest_utah_2_1(collection, full_file_name):
    soup = BeautifulSoup(open(full_file_name), "html.parser")
    user_items_list = soup.find("ul", attrs={"data-controller": "UserItemsListSimple"})
    speaker_data_str = user_items_list.attrs["data-current-context"]
    speaker_data = json.loads(speaker_data_str)
    for idx, speaker in enumerate(speaker_data["userItems"]):
        speaker_info = []
        description_soup = BeautifulSoup(speaker["description"], "html.parser")
        speaker_name = speaker["title"]
        speaker_name_slug = slugify(speaker_name)
        bio_uri = speaker["button"]["buttonLink"]
        speaker_info.append(f"Speaker Name: {speaker_name}")
        speaker_info.append(f"LinkedIn: {bio_uri}")
        speaker_info.append(f"Titles, Organizations: {description_soup.text}")
        print(f"Adding Virtual Breakout Speaker: {speaker['title']}")
        collection.upsert(
            documents=["\n".join(speaker_info)],
            metadatas=[{
                "speaker": speaker["title"],
                "type": "Virtual Speaker",
                "source": full_file_name,
            }],
            ids=[f"{speaker_name_slug}_speaker_{idx}"],
        )
        bio_content = None
        if "linkedin" in bio_uri:
            print("request on linked in")
            bio_content = get_linkedin_data(bio_uri, speaker_name_slug)
        if bio_content:
            print(f"Adding bio for {speaker['title']}")
            collection.upsert(
                documents=[bio_content],
                metadatas=[{
                    "speaker": speaker["title"],
                    "type": "Virtual Speaker Bio",
                    "source": bio_uri,
                }],
                ids=[f"{speaker_name_slug}_speaker_bio"],
            )


def get_linkedin_data(bio_uri, speaker_name_slug):
    print(f"Get linked in data for {speaker_name_slug=}")

    def _pull_leakedin_data(bio_uri):
        if not PULL_LINKEDIN:
            print(f"LinkedIn requests skipped due to {PULL_LINKEDIN=}")
            return None
        api_endpoint = "https://nubela.co/proxycurl/api/v2/linkedin"
        headers = {"Authorization": f"Bearer {PROXYCURL_API_KEY}"}
        params = {"url": bio_uri}
        response = requests.get(
            api_endpoint,
            params=params,
            headers=headers
        )
        # throttle for Nubela rate limits
        sleep(60 / NUBELA_REQUESTS_PER_MINUTE)
        return response.json()

    linkedin_datadir = os.sep.join([os.getcwd(), DATA_DIR, "linkedin.com"])
    linkedin_filename = os.sep.join([os.getcwd(), DATA_DIR, "linkedin.com", speaker_name_slug])
    linkedin_filename = linkedin_filename + ".json"

    if not os.path.exists(linkedin_datadir):
        os.makedirs(linkedin_datadir)

    file_exists = os.path.exists(linkedin_filename)
    if not file_exists:
        os.mknod(linkedin_filename)

    dest_file = open(linkedin_filename, "r+")
    if not file_exists or RESET_LINKEDIN_DATA:
        # make call and cache for future use
        bio_data = _pull_leakedin_data(bio_uri=bio_uri)
        if bio_data:
            print(f"writing {bio_data=} to {linkedin_filename=}")
            json.dump(bio_data, dest_file)
    else:
        # use stored data
        print(f"reading from cache for {linkedin_filename=}")
        try:
            bio_data = json.load(dest_file)
        except JSONDecodeError:
            print(f"Error reading linkedin data from {linkedin_filename=}")
            bio_data = None
    bio_content = None
    # 'code' only exists if the user record isn't found
    if bio_data and not bio_data.get("code"):
        template = env.get_template("linkedin_bios.jinja2")
        bio_content = template.render(bio=bio_data)
        # write the template data for review
        bio_file = Path(TEMPLATED_DATA_STORE_PATH, "bio", slugify(bio_data["full_name"]) + ".txt")
        bio_file.parent.mkdir(exist_ok=True, parents=True)
        with open(bio_file, "w") as f:
            f.write(bio_content)

    return bio_content


SPESHUL_CASES = {
    "good-tech-fest-utah-2-1": handle_good_tech_fest_utah_2_1,
    "ai-data-science-track.html": handle_tracks,
    "cyber-security-track.html": handle_tracks,
    "engineering-track.html": handle_tracks,
    "technical-leadership-management-track.html": handle_tracks,
    "product-development-management-track.html": handle_tracks,
    "governance-collaboration-track.html": handle_tracks,
    "ethics-responsibility-track.html": handle_tracks,
}

if __name__ == "__main__":
    vector_store = initialize_vector_store(
        collection_name=COLLECTION_NAME,
        reset_vector_store=RESET_VECTOR_STORE,
    )
    populate_data_from_website(vector_store)
