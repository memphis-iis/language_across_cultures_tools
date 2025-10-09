# this script is used to process UNGA Videos
#
import os
import sys
import cv2
import pandas as pd
import rembg
import concurrent.futures

#write to processing csv that handles which file this host is processing, and the status of the processing so we can resume and not duplicate work
def write_to_processing_csv(input_folder, filename, function, status):
    #check if the processing csv exists
    processing_csv = os.path.join(input_folder, 'processing.csv')
    if not os.path.isfile(processing_csv):
        df = pd.DataFrame(columns=['filename', 'function', 'status', 'host'])
        df.to_csv(processing_csv, index=False)
    #write to the processing csv
    df = pd.read_csv(processing_csv)
    df = pd.concat([df, pd.DataFrame({'filename':[filename], 'function':[function], 'status':[status], 'host':[os.uname().nodename]})], ignore_index=True)
    df.to_csv(processing_csv, index=False)
#read from processing csv to check if the file has been processed or is being processed
def is_processing(input_folder, filename):
    processing_csv = os.path.join(input_folder, 'processing.csv')
    if not os.path.isfile(processing_csv):
        return False
    df = pd.read_csv(processing_csv)
    return df[df['filename'] == filename].shape[0] > 0

def is_completed(input_folder, filename, function):
    processing_csv = os.path.join(input_folder, 'processing.csv')
    if not os.path.isfile(processing_csv):
        return False
    df = pd.read_csv(processing_csv)
    return df[(df['filename'] == filename) & (df['function'] == function) & (df['status'] == 'completed')].shape[0] > 0


#extract_frames
def extract_frames(file, output_folder):
    #check if the file is being processed
    if is_processing(output_folder, file):
        print(f'{file} already being processed')
        return
    #check if the file has been processed
    if is_completed(output_folder, file, 'extract_frames'):
        print(f'{file} already processed')
        return
    #lock the file
    write_to_processing_csv(output_folder, file, 'extract_frames', 'processing')
    # Get the full path of the input file
    input_path = os.path.join(file)
    print(f'Extracting frames from {file}')
    # Load the video file
    video = cv2.VideoCapture(input_path)
    # Get the number of frames
    frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    # Extract the frames
    for i in range(frame_count):
        # Read the frame
        success, frame = video.read()
        if not success:
            print(f'Error: Frame {i} not read')
            break
        # Save the frame
        frame_path = os.path.join(output_folder, f'{file}_{i}.jpg')
        print(f'Writing frame {i} to {frame_path}')
        cv2.imwrite(frame_path, frame)
    #unlock the file and mark as completed
    write_to_processing_csv(output_folder, file, 'extract_frames', 'completed')
    print(f'Frames extracted from {file}')



def remove_background_of_files(input_folder, output_folder):
    files = [f for f in os.listdir(input_folder) if f.endswith('.jpg') and not f.startswith('#')]
    print(f'Files: {files.shape[0]}')
    #iterate over the files
    for filename in files:
        if is_processing(input_folder, filename, 'remove_background_of_files'):
            print(f'{filename} already processed')
            continue
        if not is_completed(input_folder, filename, 'extract_frames'):
            print(f'{filename} has not been processed to extract frames')
            continue
        #lock the file
        write_to_processing_csv(input_folder, filename, 'remove_background_of_files', 'processing')
        # Get the full path of the input file
        input_path = os.path.join(input_folder, filename)
        print(f'Removing background from {filename}')
        # Load the image file
        image = cv2.imread(input_path)
        # Remove the background
        output_path = os.path.join(output_folder, f'#{filename}')
        cv2.imwrite(output_path, rembg.remove(image))
        #delete the original file
        os.remove(input_path)
        #unlock the file and mark as completed
        write_to_processing_csv(input_folder, filename, 'remove_background_of_files', 'completed')
        print(f'Background removed from {filename}')

def multithread_remove_background_of_files(input_folder, output_folder, workers=4):
    #use concurrent futures to multithread the extraction of frames
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        executor.map(remove_background_of_files, input_folder, output_folder)
    
def combine_frames_into_wmv(input_folder, output_folder):
    files = [f for f in os.listdir(input_folder) if f.endswith('.jpg') and not f.startswith('#')]
    #iterate over the files
    for filename in files:
        if is_processing(input_folder, filename, 'combine_frames_into_wmv'):
            print(f'{filename} already processed')
            continue
        if not is_completed(input_folder, filename, 'remove_background_of_files'):
            print(f'{filename} has not been processed to remove background')
            continue
        #lock the file
        write_to_processing_csv(input_folder, filename, 'combine_frames_into_wmv', 'processing')
        # Get the full path of the input file
        input_path = os.path.join(input_folder, filename)
        print(f'Combining frames into WMV for {filename}')
        # Load the image file
        image = cv2.imread(input_path)
        # Remove the background
        output_path = os.path.join(input_folder, f'#{filename}')
        cv2.imwrite(output_path, rembg.remove(image))
        #unlock the file and mark as completed
        write_to_processing_csv(input_folder, filename, 'combine_frames_into_wmv', 'completed')
        print(f'Background removed from {filename}')
    
def multithread_combine_frames_into_wmv(input_folder, output_folder, workers=4):
    #use concurrent futures to multithread the extraction of frames
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        executor.map(combine_frames_into_wmv, input_folder, output_folder)

def main_function(input_folder, output_folder_wmv):
    #this function provides the main functionality of the script
    #we prioritize the extraction of frames first, then removing the background, then combining the frames into a WMV file
    #we will use multithreading to speed up the process
    #if no frames are available for extraction, we go to the next step
    
    #for each file in the input folder, extract the frames
    wmvs = [f for f in os.listdir(input_folder) if f.endswith('.wmv') and not f.startswith('#')]

    paths = [os.path.join(input_folder, f) for f in wmvs]
    #use concurrent futures to multithread the extraction of frames
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(extract_frames, paths, input_folder)



    
# main to set arguments
if __name__ == '__main__':
    # usage input_folder, 2nd argument is the function to run
    if len(sys.argv) != 3:
        print('Usage: python process_unga_videos.py input_folder output_folder_wmv')
        sys.exit(1)
    input_folder = sys.argv[1]
    output_folder_wmv = sys.argv[2]
    print(f'input_folder: {input_folder}, output_folder_wmv: {output_folder_wmv}')
    main_function(input_folder, output_folder_wmv)



