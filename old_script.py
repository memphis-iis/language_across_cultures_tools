import os
import shutil
import time
import concurrent.futures
from pathlib import Path
import threading
import sys
import socket
import re
import queue
import subprocess
import tempfile
from tqdm import tqdm
import cv2
import mysql.connector
import subprocess
ENABLE_REMBG = False
CUSTOM_TEMP_DIR = False
if sys.platform != "darwin" or ENABLE_REMBG:
    from rembg import remove
else:
    print("rembg is not supported on macOS. Skipping...")

#if the custom temp dir is set, we use that instead of the default temp dir
CUSTOM_TEMP_DIR = os.getenv("CUSTOM_TEMP_DIR")
if CUSTOM_TEMP_DIR:
    tempfile.tempdir = CUSTOM_TEMP_DIR

# Database connection
MYSQL_HOST = "iisml-Precision-7920-tower.uom.memphis.edu"
MYSQL_USER = "root"
MYSQL_PASSWORD = "governmentSecrets"
MYSQL_DB = "unga"
MYSQL_PORT = 3306


# Constants and Configuration
TEMP_DIR = "temp13_frames"
OUTPUT_DIR = "output_videos"
CHUNK_SIZE = 20  # Number of frames to process per chunk
DISK_SPACE_THRESHOLD = 200 * 1024 * 1024 * 1024  # 200 GB

# mutex to ensure thread safety
mutex = threading.Lock()

# Create a queue for SQLite write/read operations
sqlite_write_queue = queue.Queue()
sqlite_read_queue = queue.Queue()

def ensure_dir(directory):
    """Ensure the existence of a directory."""
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
    except OSError as e:
        print(f"Error creating directory {directory}: {e}")
    """Ensure the script has proper permissions to read, write, and delete files."""
    try:
        #print if the script has the right permissions
        print(f"Checking permissions for directory {directory}")
        #if linux or macos we use chmod
        if sys.platform != "win32":
            os.chmod(directory, 0o777)
        else:
            #if windows we use icacls
            subprocess.run(["icacls", directory, "/grant", f"{os.getlogin()}:(OI)(CI)F", "/T", "/Q"])
        print(f"Permissions set for directory {directory} to read, write, and delete files.")
    except OSError as e:
        print(f"Error changing permissions for directory {directory}: {e}")




def init_db():
    """Initialize the SQL database and create tables if they don't exist."""
    while True:
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                port=MYSQL_PORT
            )
            cursor = conn.cursor()

            # Create the database if it does not exist
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB}")
            conn.commit()
            cursor.close()
            conn.close()

            # Reconnect to the newly created database
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB,
                port=MYSQL_PORT
            )
            cursor = conn.cursor()

            # Create the tables if they do not exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chunk_locks (
                    video_name VARCHAR(255),
                    chunk_index INTEGER,
                    locked BOOLEAN,
                    hostname VARCHAR(255),
                    PRIMARY KEY (video_name, chunk_index)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chunk_states (
                    video_name VARCHAR(255),
                    chunk_index INTEGER,
                    state VARCHAR(255),
                    PRIMARY KEY (video_name, chunk_index)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_locks (
                    video_name VARCHAR(255) PRIMARY KEY,
                    locked BOOLEAN,
                    hostname VARCHAR(255)
                )
            ''')
            conn.commit()
            cursor.close()
            conn.close()
            break
        except mysql.connector.Error as e:
            print(f"SQL Connection error: {e}. Retrying...")
            time.sleep(1)

# TO SHOW ALL LOCKS AND THEIR HOSTNAMES PLEASE EXECUTE THIS QUERY:
# SELECT * FROM chunk_locks;
# SELECT * FROM video_locks;
# SELECT * FROM chunk_states;



def update_chunk_state(video_name, chunk_index, state):
    """Update the state of a chunk in the database."""
    while True:
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB
            )
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO chunk_states (video_name, chunk_index, state)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                state = VALUES(state)
            ''', (video_name, chunk_index, state))
            conn.commit()
            conn.close()
            break
        except mysql.connector.Error as e:
            print(f"SQLite write error: {e}. Retrying...")
            time.sleep(1)

def get_video_chunk_state(video_name):
    """Get the state of all chunks for a video from the database."""
    while True:
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB
            )
            cursor = conn.cursor()
            cursor.execute('''
                SELECT state FROM chunk_states
                WHERE video_name = %s
            ''', (video_name,))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except mysql.connector.Error as e:
            print(f"SQLite read error: {e}. Retrying...")
            time.sleep(1)

def get_chunk_state(video_name, chunk_index):
    """Get the state of a chunk from the database."""
    while True:
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB
            )
            cursor = conn.cursor()
            cursor.execute('''
                SELECT state FROM chunk_states
                WHERE video_name = %s AND chunk_index = %s
            ''', (video_name, chunk_index))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except mysql.connector.Error as e:
            print(f"SQLite read error: {e}. Retrying...")
            time.sleep(1)
def lock_chunk(video_name, chunk_index):
    print(f"Locking chunk {chunk_index} of {video_name}.")
    """Lock a chunk for processing."""
    while True:
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB
            )
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO chunk_locks (video_name, chunk_index, locked, hostname)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                locked = VALUES(locked),
                hostname = VALUES(hostname)
            ''', (video_name, chunk_index, True, socket.gethostname()))
            conn.commit()
            conn.close()
            break
        except mysql.connector.Error as e:
            print(f"SQLite lock error: {e}. Retrying...")
            time.sleep(1)

def unlock_chunk(video_name, chunk_index):
    """Unlock a chunk after processing."""
    print(f"Unlocking chunk {chunk_index} of {video_name}.")
    while True:
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB
            )
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM chunk_locks
                WHERE video_name = %s AND chunk_index = %s
            ''', (video_name, chunk_index))
            conn.commit()
            conn.close()
            break
        except mysql.connector.Error as e:
            print(f"SQLite unlock error: {e}. Retrying...")
            time.sleep(1)

def is_chunk_locked(video_name, chunk_index):
    """Check if a chunk is locked."""
    while True:
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB
            )
            cursor = conn.cursor()
            cursor.execute('''
                SELECT locked FROM chunk_locks
                WHERE video_name = %s AND chunk_index = %s
            ''', (video_name, chunk_index))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else False
        except mysql.connector.Error as e:
            print(f"SQLite read error: {e}. Retrying...")
            time.sleep(1)

def lock_video(video_name):
    """Lock a video for processing."""
    print(f"Locking video {video_name}")
    while True:
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB
            )
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO video_locks (video_name, locked, hostname)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                locked = VALUES(locked),
                hostname = VALUES(hostname)
            ''', (video_name, True, socket.gethostname()))
            conn.commit()
            conn.close()
            break
        except mysql.connector.Error as e:
            print(f"SQLite lock error: {e}. Retrying...")
            time.sleep(1)

def unlock_video(video_name):
    print(f"Unlocking video {video_name}")
    """Unlock a video after processing by deleting the lock."""
    while True:
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB
            )
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM video_locks
                WHERE video_name = %s
            ''', (video_name,))
            conn.commit()
            conn.close()
            break
        except mysql.connector.Error as e:
            print(f"SQLite unlock error: {e}. Retrying...")
            time.sleep(1)

def is_video_locked(video_name):
    """Check if a video is locked."""
    attempts = 5
    while attempts > 0:
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB
            )
            cursor = conn.cursor()
            cursor.execute('''
                SELECT locked FROM video_locks
                WHERE video_name = %s
            ''', (video_name,))
            row = cursor.fetchone()
            conn.close()
            #if no row is returned, we return False
            if not row:
                return False
            return True
        except mysql.connector.Error as e:
            print(f"SQLite read error: {e}. Retrying...")
            attempts -= 1
            time.sleep(1)
    return False


def extract_frames(video_path, temp_dir):
    """Extract frames from a video using FFmpeg."""
    print(f"extract_frames: {video_path, temp_dir}")
    video_name = Path(video_path).stem
    extracted_frames_dir = os.path.join(tempfile.gettempdir(), 'temp_frames', video_name)
    ensure_dir(extracted_frames_dir)
    lock_video(video_name)
    local_video_path = os.path.join(tempfile.gettempdir(), os.path.basename(video_path))
    ensure_dir(tempfile.gettempdir())
    # Copy the video to the local directory
    shutil.copy(video_path, local_video_path)
    
    # Extract frames using FFmpeg
    output_pattern = os.path.join(extracted_frames_dir, f"{video_name}_frame_%04d.png")
    #get the fps of the video
    fps = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "default=noprint_wrappers=1:nokey=1", local_video_path], stdout=subprocess.PIPE)
    print(f"Extracting frames from {local_video_path} to {extracted_frames_dir} at {fps.stdout.decode().strip()} fps.")
    command = [
        'ffmpeg',
        '-i', local_video_path,
        '-vf', 'fps=' + fps.stdout.decode().strip(),
        output_pattern
    ]
    subprocess.run(command, check=True)
    print(f"Frames extracted to {extracted_frames_dir}")

    # Set all chunks to extracted
    chunk_count = len(os.listdir(extracted_frames_dir)) // CHUNK_SIZE
    for chunk_index in range(chunk_count):
        update_chunk_state(video_name, chunk_index, "extracted")

    # Remove the local copy of the video file
    print(f"Removing local video {local_video_path}.")
    os.remove(local_video_path)
    print(f"Local video {local_video_path} removed.")
    # Copy the frames back to the network storage, overwriting the remote frames
    print(f"Copying extracted frames back to network storage.")
    frame_files = os.listdir(extracted_frames_dir)
    with tqdm(total=len(frame_files), unit='frame', desc="Copying frames to network storage") as pbar:
        for frame in frame_files:
            try:
                shutil.copy(os.path.join(extracted_frames_dir, frame), os.path.join(temp_dir, video_name, frame))
            except shutil.SameFileError:
                pass
            except PermissionError:
                #if the file exists, we remove it and copy it again
                if os.path.exists(os.path.join(temp_dir, video_name, frame)):
                    #if linux or macos, use os.system
                    if sys.platform != "win32":
                        os.system(f"rm {os.path.join(temp_dir, video_name, frame)}")
                        os.system(f"cp {os.path.join(extracted_frames_dir, frame)} {os.path.join(temp_dir, video_name, frame)}")

                    else:
                        #if windows, use subprocess.run
                        subprocess.run(["del", os.path.join(temp_dir, video_name, frame)], check=True)  
                        os.system(f"copy {os.path.join(extracted_frames_dir, frame)} {os.path.join(temp_dir, video_name, frame)}")
                    
                else:
                    #throw the error if it is not a permission error
                    raise

            pbar.update(1)
    print(f"Extracted frames copied back to network storage. Removing local frames.")
    shutil.rmtree(extracted_frames_dir)
    # Unlock the video
    unlock_video(video_name)
    

def print_lock_file_status():
    return

def remove_background_from_chunk(frame_chunk):
    """Remove the background from a chunk of frames using rembg."""
    for frame_path in frame_chunk:
        print(f"Processing frame {frame_path}")
        input_image = cv2.imread(os.path.join(frame_path))
        output_image = remove(input_image)
        cv2.imwrite(os.path.join(os.path.join(frame_path)), output_image)

def process_frames_in_chunks(video_name, frames_dir, chunk_size):
    """Process frames in chunks, removing backgrounds."""
    print(f"process_frames_in_chunks: {video_name, frames_dir, chunk_size}")
    # frame_files should be the whole path to the file
    frame_files = sorted(os.listdir(frames_dir))
    #frame_files should now have the full path to the file
    frame_files = [os.path.join(frames_dir, file) for file in frame_files]

    total_chunks = (len(frame_files) + chunk_size - 1) // chunk_size

    

    for chunk_index in range(total_chunks):
        try:
            #lock the chunk
            if is_chunk_locked(video_name, chunk_index):
                print(f"Chunk {chunk_index} of {video_name} is already locked. Skipping...")
                continue
            lock_chunk(video_name, chunk_index)
            chunk_start = chunk_index * chunk_size
            chunk_end = min((chunk_index + 1) * chunk_size, len(frame_files))
            frame_chunk = frame_files[chunk_start:chunk_end]
            remove_background_from_chunk(frame_chunk)

            # Update chunk state after processing
            update_chunk_state(video_name, chunk_index, "background_removed")
            print(f"Chunk {chunk_index} of {video_name} processed successfully.")
            #unlock the chunk
            unlock_chunk(video_name, chunk_index)
        except Exception as e:
            print(f"Error processing chunk {chunk_index} of {video_name}: {e}")
            #wait for user input
            #unlock the chunk
            unlock_chunk(video_name, chunk_index)
            

def process_chunk(video_name, frames_dir, chunk_index, chunk_size):
    print(f"process_chunk: {video_name, frames_dir, chunk_index, chunk_size}")
    """Process a single chunk of frames for background removal."""
    ensure_dir(TEMP_DIR)
    print(f"process_chunk: {video_name, frames_dir, chunk_index, chunk_size}")
    local_chunk_dir = None  # Ensure local_chunk_dir is defined

    try:
        # Load frame chunk
        frame_files = sorted(os.listdir(frames_dir))
        chunk_start = chunk_index * chunk_size
        chunk_end = min((chunk_index + 1) * chunk_size, len(frame_files))
        frame_chunk = frame_files[chunk_start:chunk_end]

        if not frame_chunk:
            print(f"No frames found in chunk {chunk_index} of {video_name}.")
            return

        # Copy the chunk of frames locally
        local_chunk_dir = os.path.join(tempfile.gettempdir(), 'temp_chunk', video_name, str(chunk_index))
        print("Local chunk directory: ", local_chunk_dir)
        ensure_dir(local_chunk_dir)
        local_frame_chunk = []
        for frame_file in frame_chunk:
            print(f"Copying frame {frame_file} to local chunk directory.")
            local_frame_path = os.path.join(local_chunk_dir, os.path.basename(frame_file))
            shutil.copy(os.path.join(frames_dir, frame_file), local_frame_path)
            local_frame_chunk.append(local_frame_path)

       # Process background removal
        remove_background_from_chunk(local_frame_chunk)

        #remove the remote frames
        for frame in os.listdir(os.path.join(frames_dir)):
            os.remove(os.path.join(frames_dir, frame))
        # Copy the processed frames back to the network storage
        for local_frame_path in local_frame_chunk:
            try:
                shutil.copy(local_frame_path, frames_dir)
            except shutil.SameFileError:
                pass
            except PermissionError:
                #if the file exists, we remove it and copy it again
                if os.path.exists(os.path.join(frames_dir, os.path.basename(local_frame_path))):
                    #if linux or macos, use os.system
                    path = os.path.join(frames_dir, os.path.basename(local_frame_path))
                    if sys.platform != "win32":
                        os.system(f"rm {path}")
                        os.system(f"cp {local_frame_path} {path}")

                    else:
                        #if windows, use subprocess.run
                        subprocess.run(["del", path], check=True)
                        os.system(f"copy {local_frame_path} {path}")
                        
                else:
                    #throw the error if it is not a permission error
                    raise   

            

        # Update chunk state to 'background_removed'
        update_chunk_state(video_name, chunk_index, "background_removed")
        print(f"Chunk {chunk_index} of {video_name} processed successfully.")
    except Exception as e:
        print(f"Error processing chunk {chunk_index} of {video_name}: {e}")
    finally:
        # Clean up local chunk directory
        if local_chunk_dir:
            try:
                shutil.rmtree(local_chunk_dir)
            except Exception as e:
                print(f"Error cleaning up local chunk directory {local_chunk_dir}: {e}")

def print_file_lock_status():
    #print all locked videos and chunks with their hostnames
    conn = sqlite3.connect(LOCK_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM video_locks')
    rows = cursor.fetchall()
    print("Current video lock status:")
    for row in rows:
        print(f"Video: {row[0]}, Locked: {row[1]}, Hostname: {row[2]}")
    cursor.execute('SELECT * FROM chunk_locks')
    rows = cursor.fetchall()
    print("Current chunk lock status:")
    for row in rows:
        print(f"Video: {row[0]}, Chunk: {row[1]}, Locked: {row[2]}, Hostname: {row[3]}")
    conn.close()


def reassemble_video(frames_dir, output_video_path):
    """Reassemble frames back into a video."""
    frame_files = sorted(frames_dir.glob("*.png"))
    if not frame_files:
        print("No frames found to assemble.")
        return

    first_frame = cv2.imread(str(frame_files[0]))
    height, width = first_frame.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(os.path.join(output_video_path), fourcc, 30, (width, height))

    with tqdm(total=len(frame_files), unit='frame', desc="Reassembling video") as pbar:
        for frame_file in frame_files:
            frame = cv2.imread(str(frame_file))
            out.write(frame)
            pbar.update(1)
    out.release()
def process_chunks_across_videos(video_dir, chunk_size):
    all_videos_processed = False
    while not all_videos_processed:
        """Process chunks for all videos in the directory."""
        print(f"process_chunks_across_videos: {video_dir, chunk_size}")
        video_files = list(Path(video_dir).glob("*.mp4"))

        #filter video_files to only include videos whose chunks have been extracted or background removed
        started_videos = []
        local_videos = []
        

        for video_path in video_files:
            #if the video is already in the list of started videos, we skip
            if video_path in started_videos:
                continue
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            #if the folder for the video does not exist, we skip
            if not os.path.exists(os.path.join(TEMP_DIR, video_name)):
                continue
            total_frames = len(os.listdir(os.path.join(TEMP_DIR, video_name)))
            total_chunks = (total_frames + chunk_size - 1) // chunk_size
            chunk_states = get_video_chunk_state(video_name)
            all_chunks_processed = all(state == "background_removed" for state in chunk_states)
            all_chunks_extracted = all(state == "extracted" for state in chunk_states)
            if all_chunks_processed or all_chunks_extracted:
                #if the frame directory contains 0 frames, we skip
                if len(os.listdir(os.path.join(TEMP_DIR, video_name))) == 0:
                    continue
                started_videos.append(video_path)
            #if there is a a local copy of the video, we append it to the list of local videos
            if os.path.exists(os.path.join(tempfile.gettempdir(), os.path.basename(video_path))):
                print(f"Local copy of video {video_path} found.")
                local_videos.append(os.path.join(tempfile.gettempdir(), os.path.basename(video_path)))

        #reorder the list of started videos to have the local videos first
        started_videos = local_videos + [video for video in started_videos if video not in local_videos]


        
                    
        for video_path in started_videos:
            print(f"Processing video {video_path}")
            #if there are no chunk states in the database, we skip
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            all_chunk_states = get_video_chunk_state(video_name)
            if not all_chunk_states:
                print(f"No chunk states found in the database for {video_name}. Skipping...")
                print(f"Video path: {video_path}")
                #if its in the list of started videos, we remove it
                if video_path in started_videos:
                    try:
                        started_videos.remove(video_path)
                    except ValueError:
                        continue
                continue
                    

            print(f"Started videos count: {len(started_videos)}")
                        
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            frames_dir = os.path.join(TEMP_DIR, video_name)
            try:

                ensure_dir(frames_dir)                
                total_frames = len(os.listdir(os.path.join(TEMP_DIR, video_name)))
                total_chunks = (total_frames + chunk_size - 1) // chunk_size

                def decide_what_to_do(video_name, chunk_index):
                    print(f"Processing chunk {chunk_index} of {video_name}.")
                    try:
                        #check if the video is locked again, if it is we skip
                        if is_video_locked(video_name):
                            print(f"Video {video_name} is already locked. Skipping...")
                            return
                        # Check for existing state (handle missing state)
                        chunk_state = get_chunk_state(video_name, chunk_index)
                        print(f"Chunk {chunk_index} of {video_name} state: {chunk_state}")

                        if chunk_state == "background_removed":
                            print(f"Chunk {chunk_index} of {video_name} is already processed.")
                        #dont allow darwin to process the chunk
                        if chunk_state == "extracted" and sys.platform != "darwin" and ENABLE_REMBG:
                            print(f"Chunk {chunk_index} of {video_name} is queued for background removal. PCT: {chunk_index/total_chunks}")
                            process_chunk(video_name, frames_dir, chunk_index, chunk_size)
                            #unlock the chunk
                            unlock_chunk(video_name, chunk_index)


                        
                    except Exception as e:
                        print(f"Error processing chunk {chunk_index} of {video_name}: {e}")
                        #wait for user input
                        
                        # Ensure lock is released
                        unlock_chunk(video_name, chunk_index)
                        unlock_video(video_name)

                # Iterate through all the chunks and check if they are processed,
                # if not we add them as a task to the executor
                print(f"Total chunks: {total_chunks}")
                #if no chunks are in the database, skip
                all_chunks_in_db = get_video_chunk_state(video_name)
                if not all_chunks_in_db:
                    print(f"No chunks found in the database for {video_name}. Skipping...")
                    #check
                for chunk_index in range(total_chunks):
                    #if the video is locked, we break
                    if is_video_locked(video_name):
                        print(f"Video {video_name} is already locked. Skipping...")
                        break
                    print(f"Processing chunk {chunk_index} of {video_name} with state {get_chunk_state(video_name, chunk_index)}")
                    decide_what_to_do(video_name, chunk_index)
                    time.sleep(0.2)




            finally:
                # Unlock the video
                unlock_video(video_name)

        #if we are here. we find if any of the videos have all their chunks background removed. If so, reassemble the video
        for video_path in video_files:
            print(f"Checking if video {video_path} is ready for reassembly.")
            #if the folder for the video does not exist, we skip
            if not os.path.exists(os.path.join(TEMP_DIR, video_name)):
                continue
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            try:
                total_frames = len(os.listdir(os.path.join(TEMP_DIR, video_name)))
                total_chunks = (total_frames + chunk_size - 1) // chunk_size
            except FileNotFoundError:
                continue
            all_chunk_states = get_video_chunk_state(video_name)
            all_chunks_processed = all(state == "background_removed" for state in all_chunk_states)
            count_of_all_processed_chunks = len([state for state in all_chunk_states if state == "background_removed"])
            if all_chunks_processed and count_of_all_processed_chunks == total_chunks:
                print(f"Reassembling video {video_name}.")
                reassemble_video(Path(os.path.join(TEMP_DIR, video_name)), os.path.join(OUTPUT_DIR, f"{video_name}.mp4"))
                print(f"Video {video_name} reassembled.")
                #remove the video from the list of started videos
                if video_path in started_videos:
                    try:
                        started_videos.remove(video_path)
                    except ValueError:
                        continue
                #set the chunks to reassembled
                for i in range(total_chunks):
                    update_chunk_state(video_name, i, "reassembled")
                #unlock the video
                unlock_video(video_name)
                #we only do one video at a time, so break the for loop
                break
            print(f"Video {video_name} is not ready for reassembly, checking if it needs processing.")
            all_chunks_extracted = all(state == "extracted" for state in all_chunk_states)
            count_of_all_extracted_chunks = len([state for state in all_chunk_states if state == "extracted"])
            if all_chunks_extracted and count_of_all_extracted_chunks == total_chunks:
                print(f"Processing frames for video {video_name}.")
                process_frames_in_chunks(video_name, os.path.join(TEMP_DIR, video_name), chunk_size)
                #we only do one video at a time, so break the for loop
                break
            else:
                print(f"Video {video_name} is not ready for processing or reassembly.")
                
        print("All videos processed. Checking for unprocessed videos...")
        #if we are here, all videos that have been started have been processed. Then we iterate over the remaining videos to extract frames
        for video_path in video_files:
            #if the video is locked, we skip
            if is_video_locked(video_name):
                print(f"Video {video_name} is already locked. Skipping...")
                #put this video at the end of the list of video_files
                video_files.remove(video_path)
                video_files.append(video_path)

            video_name = os.path.splitext(os.path.basename(video_path))[0]
            #frame output path for the video
            frames_dir = os.path.join(TEMP_DIR, video_name)
            ensure_dir(frames_dir)
            #if the frame directory exists and has the same number of frames as the video, we skip
            video = cv2.VideoCapture(os.path.join(video_dir, video_name + ".mp4"))
            total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            print(f"Total frames: {total_frames}, Extracted frames: {len(os.listdir(frames_dir))}")
            if os.path.exists(frames_dir) and len(os.listdir(frames_dir)) == total_frames:
                print(f"Video {video_name} has already been extracted. Skipping...")
                #set the state of all chunks to extracted
                total_frames = len(os.listdir(os.path.join(TEMP_DIR, video_name)))
                total_chunks = (total_frames + chunk_size - 1) // chunk_size
                for i in range(total_chunks):
                    update_chunk_state(video_name, i, "extracted")
                #check each chunk to see if it is extracted
            if video_path not in started_videos:
                if is_video_locked(video_name):
                    print(f"Video {video_name} is already locked. Skipping...")
                    continue
                print(f"Extracting frames for {video_name}.")
                #lock the video
                extract_frames(video_path, TEMP_DIR)
                #we only do one video at a time, so break the for loop
                break



        
        
        # Check disk space and wait for a while
        disk_space = shutil.disk_usage(".")[2]
        print(f"Disk space: {disk_space / 1024 / 1024 / 1024:.2f} GB")

        if disk_space < DISK_SPACE_THRESHOLD:
            print("Low disk space. Waiting for space to be freed up...")
            time.sleep(60)

def sanitize_filename(filename):
    """Sanitize the filename to contain only alphanumeric characters and underscores and periods."""
    return re.sub(r"[^a-zA-Z0-9_.]", "_", filename)


def main(video_dir):
    """Main function to continuously process video chunks until completion."""
    ensure_dir(TEMP_DIR)
    ensure_dir(OUTPUT_DIR)
    print("Initializing database...")
    init_db()

    # Load metadata and initialize states
    videos = [str(file) for file in os.listdir(video_dir) if file.endswith(".mp4")]
    print(f"Found {len(videos)} videos.")

    # Rename the videos to not have any non-alphanumeric characters
    print("Renaming videos for processing...")
    for video in videos:
        sanitized_name = sanitize_filename(video)
        if sanitized_name != video:
            print(f"Renaming {video} to {sanitized_name}")
            os.rename(os.path.join(video_dir, video), os.path.join(video_dir, sanitized_name))

    # Reload the videos
    videos = [str(file) for file in os.listdir(video_dir) if file.endswith(".mp4")]

    # Process chunks across all videos
    process_chunks_across_videos(video_dir, CHUNK_SIZE)

if __name__ == "__main__":
    init_db()  # Ensure the database is initialized
    #add a flag to specify to remove all locks from the database
    if len(sys.argv) > 2:
        if sys.argv[2] == "--reset":
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB
            )
            cursor = conn.cursor()
            cursor.execute('DELETE FROM chunk_locks')
            cursor.execute('DELETE FROM chunk_states')
            cursor.execute('DELETE FROM video_locks')
            conn.commit()
            conn.close()
            print("All locks removed from the database.")


    main(sys.argv[1])
