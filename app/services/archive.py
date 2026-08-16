import tempfile
import zipfile
import shutil
import os

def extract_zip(zip_path: str):
    # 1. Create the temp directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 2. Try to extract the files securely
        with zipfile.ZipFile(zip_path, "r") as archive:
            
            # --- ZIP SLIP PROTECTION ---
            for member in archive.namelist():
                member_path = os.path.realpath(os.path.join(temp_dir, member))
                if not member_path.startswith(os.path.realpath(temp_dir) + os.sep):
                    raise ValueError(f"Unsafe path in zip (Zip Slip detected): {member}")
            
            # If all checks pass, it is safe to extract
            archive.extractall(temp_dir)
            
        # 3. Gather the list of extracted files
        extracted_files = []
        for root, _, files in os.walk(temp_dir):
            for file in files:
                extracted_files.append(os.path.join(root, file))
                
        return temp_dir, extracted_files
        
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise e