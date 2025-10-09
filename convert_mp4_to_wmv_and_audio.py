import os
from moviepy.editor import VideoFileClip
import multiprocessing

# Specify the input folder containing the WMA files
input_folder = '/media/rusty/Data2/UNGA/UNGA_78/mp4/'

# Specify the output folder for WMA and MP3 files
output_folder = '/media/rusty/Data2/UNGA/UNGA_78/'

# Create the output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

for filename in os.listdir(input_folder):
    if filename.endswith('.mp4'):
        #check if the output files already exist, if so, skip


        # Get the full path of the input file
        input_path = os.path.join(input_folder, filename)

        #output file names
        stripped_filename = filename.split('.')[0]
        output_wmv_file = os.path.join(output_folder, stripped_filename + '.wmv')
        output_mp3_file = os.path.join(output_folder, stripped_filename + '.mp3')
        
        #check if the output files already exist
        if os.path.exists(output_wmv_file) and os.path.exists(output_mp3_file):
            print(f'{filename} already exists')
            continue

        # Load the video file
        print(f'Converting {filename} to WMV and MP3: input_path: {input_path}')
        video = VideoFileClip(input_path)
        
        #check if the wmv file already exists
        if os.path.exists(output_wmv_file):
            print(f'{filename} already exists')
            continue
        else:
            try:
                # Export the video to WMV format
                video.write_videofile(output_wmv_file, codec='wmv2')
            except:
                print(f'Error converting {filename} to WMV')
                #write to a file so we can check later
                with open('error_files.txt','a') as error_file:
                    error_file.write(f'{filename}\n')
                continue
            

        # Get the audio from the video
        #check if the mp3 file already exists
        audio = video.audio

        if os.path.exists(output_mp3_file):
            print(f'{filename} already exists')
            continue
        try:
            # Export the audio to MP3 format
            multiprocessing.Process(target=audio.write_audiofile, args=(output_mp3_file,)).start()
            audio.write_audiofile(output_mp3_file)
        except:
            print(f'Error converting {filename} to MP3')
            #write to a file so we can check later
            with open('error_files.txt','a') as error_file:
                error_file.write(f'{filename}\n')
            continue
    
        # Close the video and audio objects
        video.close()
        audio.close()

print("Conversion and export to WMV and MP3 completed.")