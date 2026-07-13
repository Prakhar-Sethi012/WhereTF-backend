import os

from .api import upload, needs_indexing
from .hashing import calculate_file_hash


def scan_folder(folder_path: str):
    """
    Scan an existing watched folder and upload only new/changed files.
    """

    for root, _, files in os.walk(folder_path):

        for filename in files:

            file_path = os.path.join(root, filename)

            try:
                file_hash = calculate_file_hash(file_path)

                if needs_indexing(file_path, file_hash):

                    print(f"Indexing: {file_path}")

                    response = upload(file_path)

                    print(response)

                else:

                    print(f"Skipping: {file_path}")

            except Exception as e:

                print(f"Failed: {file_path}")
                print(e)