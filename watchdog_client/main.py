import time
from .scanner import scan_folder
from watchdog.observers import Observer
from .api import get_watched_folders
from .watcher import FileWatcher

folders = get_watched_folders()
observer = Observer()

for folder in folders:

    folder_path = folder["folder_path"]

    scan_folder(folder_path)

    observer.schedule(
        FileWatcher(),
        folder_path,
        recursive=True
    )
observer.start()

print("Watching folders...")

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    observer.stop()

observer.join()