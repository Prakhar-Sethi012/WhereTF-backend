from pathlib import Path
import requests

from .config import API_URL

def get_watched_folders():

    response = requests.get(
        f"{API_URL}/watch/folders"
    )

    response.raise_for_status()

    return response.json()

def upload(file_path: str):

    with open(file_path, "rb") as f:

        response = requests.post(
            f"{API_URL}/upload/",
            files={
                "file": (Path(file_path).name, f)
            },
            data={
                "original_path": file_path
            }
        )

    response.raise_for_status()

    return response.json()

def delete(file_path: str):

    response = requests.post(
        f"{API_URL}/files/delete-by-path",
        json={
            "file_path": file_path
        }
    )

    response.raise_for_status()

    return response.json()

def modify(file_path: str):

    # Remove the old indexed version
    delete(file_path)

    # Upload and re-index the current version
    return upload(file_path)

def rename(old_path: str, new_path: str):

    response = requests.post(
        f"{API_URL}/files/rename",
        json={
            "old_path": old_path,
            "new_path": new_path
        }
    )

    response.raise_for_status()

    return response.json()

def needs_indexing(file_path: str, file_hash: str):

    response = requests.post(
        f"{API_URL}/files/needs-indexing",
        json={
            "file_path": file_path,
            "file_hash": file_hash
        }
    )

    response.raise_for_status()

    return response.json()["needs_indexing"]