from watchdog.events import FileSystemEventHandler
from .api import upload, delete, modify, rename
import time

DEBOUNCE_SECONDS = 1.5  # Time to wait before processing a file event
last_processed={}

class FileWatcher(FileSystemEventHandler):

    def on_created(self, event):

        if event.is_directory:
            return

        now = time.time()

        last_time = last_processed.get(event.src_path)

        if last_time and (now - last_time) < DEBOUNCE_SECONDS:
            return

        last_processed[event.src_path] = now

        print("Created:", event.src_path)

        try:
            time.sleep(1)
            response = upload(event.src_path)
            print(response)

        except Exception as e:
            print("Upload failed:", e)


    def on_modified(self, event):

        if event.is_directory:
            return

        now = time.time()

        last_time = last_processed.get(event.src_path)

        if last_time and (now - last_time) < DEBOUNCE_SECONDS:
            return

        last_processed[event.src_path] = now

        print("Modified:", event.src_path)

        try:
            modify(event.src_path)
            print("Successfully re-indexed.")

        except Exception as e:
            print("Modify failed:", e)

    def on_deleted(self, event):

        if event.is_directory:
            return

        print("Deleted:", event.src_path)

        try:
            response = delete(event.src_path)
            print(response)

        except Exception as e:
            print("Delete failed:", e)

    def on_moved(self, event):

        if event.is_directory:
            return

        print(f"Renamed: {event.src_path} -> {event.dest_path}")

        try:
            response = rename(event.src_path, event.dest_path)
            print(response)

        except Exception as e:
            print("Rename failed:", e)