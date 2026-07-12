import os
import tempfile
import zipfile


def extract_zip(zip_path: str):

    temp_dir = tempfile.mkdtemp()

    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(temp_dir)

    extracted_files = []

    for root, _, files in os.walk(temp_dir):
        for file in files:
            extracted_files.append(
                os.path.join(root, file)
            )

    return temp_dir, extracted_files