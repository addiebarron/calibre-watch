import os, sys, re, subprocess, datetime, time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from dotenv import load_dotenv

load_dotenv()

watch_dir = os.getenv("WATCH_DIR")
calibre_library = os.getenv("CALIBRE_SERVER_LIBRARY_URL")
calibredb_exe = (
    os.getenv("CALIBREDB_EXE") or "/Applications/calibre.app/Contents/MacOS/calibredb"
)
username = os.getenv("CALIBRE_USERNAME")
password = os.getenv("CALIBRE_PASSWORD")

def log(*args):
    return_val = print(*args)
    # Necessary for logging with mac launchd
    sys.stdout.flush()
    return return_val

def flush():
    sys.stdout.flush()
    sys.stderr.flush()

def cmd(path):
    return [
        calibredb_exe,
        "add",
        "-m",
        "ignore",
        path,
    ]


def cmd_with_content_server(path):
    return [
        calibredb_exe,
        *(["--username",
        f"{username}",] if username else []),
        *(["--password",
        f"{password}",] if password else []),
        f"--with-library={calibre_library}",
        "add",
        "-m",
        "ignore",
        path,
    ]

def run_cmd(cmd_func, path):
    return subprocess.run(cmd_func(path), text=True, capture_output=True)

def add_book(path):
    # Run calibre add command
    result = run_cmd(cmd, path)

    if result.returncode == 0:
        return result 

    # If that didn't work, try adding via content server
    log(result.stderr)
    log("Trying to add via content server instead...")
    if not calibre_library:
        log(
            (
                "Please add the CALIBRE_LIBRARY env var, then restart the program.\n"
                "See https://manual.calibre-ebook.com/generated/en/calibredb.html#id1"
            )
        )
        quit()
    
    added = False
    attempts = 0
    while not added and attempts < 5:
        result = run_cmd(cmd_with_content_server, path)
        if result.returncode != 0:
            log("Error adding via content server. Trying again in 5 seconds...")
            attempts += 1
            time.sleep(5)
        else:
            added = True
    if not added:
        log("[ERROR] Could not add book within 5 attempts.")

    return result


class Handler(FileSystemEventHandler):
    @staticmethod
    def on_any_event(event):
        if event.is_directory:
            return None
        elif event.event_type == "created":
            file_path = event.src_path
   
            # Is it a valid ebook format?
            match = re.search(r"\.(epub|mobi|pdf|lit|azw3)$", file_path, re.I)
            
            # Is this a book created by Calibre? Don't import it, if so
            dirpath = os.path.dirname(file_path)
            folder = dirpath.split('/')[-1]
            has_calibre_folder_name = re.match(r".*\s\(\d+\)", folder)
            has_metadata = os.path.exists(f"{dirpath}/metadata.opf")
            is_calibre_book = has_calibre_folder_name and has_metadata

            if match:
                ext = match.group()

                log("Ebook file created: % s. Sending to Calibre..." % file_path)
                
                if not is_calibre_book:
                    result = add_book(file_path)    
                    success = re.match(r"((Added|Merged) book ids|The following books were not added as they already exist in the database)", result.stdout);

                    if result.returncode == 0 and success:
                        os.remove(file_path)

                    log(result.stdout, result.stderr)
                    time.sleep(5) # Avoid too-quick requests to content server

                else:
                    log("File is already in Calibre. Not importing.")

        flush()

if __name__ == "__main__":
    if not watch_dir:
        log("Please add a directory via the WATCH_DIR env var.")
        quit()

    event_handler = Handler()
    observer = Observer()

    observer.schedule(event_handler, watch_dir, recursive=True)

    log(f"Listening for changes in {watch_dir}")
    observer.start()

    try:
        while observer.is_alive():
            observer.join(1)
    finally:
        observer.stop()
        observer.join()
        flush()

