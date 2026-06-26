#   edw tha kanoume 
#ffmpeg ops
#extract audio
# extract frames
#paroume metadata tou video
# Responsible for video-related tasks:

# Save uploaded video
# Extract audio with FFmpeg
# Extract frames (if needed)
# Read video metadata (duration, fps, etc.)
# Return paths to generated files

#################Extract audio

#https://stackoverflow.com/questions/9913032/how-can-i-extract-audio-from-video-with-ffmpeg
#https://www.clipcat.com/blog/a-beginners-guide-to-using-ffmpeg-in-python-for-video-processing/#extract-audio-from-a-video
#https://koshurai.medium.com/audio-extraction-from-video-python-8f7c8352a97b

import ffmpeg
import os
from pathlib import Path

# Load the video file
#input_file = ffmpeg.input('./nnVideo.mp4')

# Extract the audio and save it as an MP3 file
#input_file.output('audio.mp3', acodec='libshine').run()

#import ffmpeg
#(

    #ffmpeg.input("input.mp4")
	#.output("audio.mp3", acodec="libshine")
	#.run()
#)

def extract_audio(video_path, output_audio):

	try:
		(
			ffmpeg.input(str(video_path))
			.output(str(output_audio), acodec='pcm_s16le', ac=1, ar='16000')  #ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 44100 -ac 2 output.wav  https://superuser.com/questions/609740/extracting-wav-from-mp4-while-preserving-the-highest-possible-quality
			.overwrite_output()
			.run()                                                       #to chatgpt evgale ac=1 ar=16k
		)                                                           
		print(f"Audio extracted successfully to {output_audio}")

	except ffmpeg.Error as e:
		stderr = e.stderr.decode(errors='replace') if e.stderr else str(e)
		raise RuntimeError(f"Audio extraction failed: {stderr}") from e




##########extract frames  douleuei apla to kanw comment giati pernei ligo wra gia na to kanei 

# def extract_frames(video_path, output_dir):
#     try:

#         output_dir = Path(output_dir)
#         output_dir.mkdir(parents=True, exist_ok=True)
#         output_pattern = output_dir / 'frame_%04d.jpg'
        
#         (
#             ffmpeg.input(str(video_path))                             
#             .filter('fps', fps=1/5)    # Extract 1 frame per 5 sec
#             .output(str(output_pattern))  #ffmpeg -i big_buck_bunny_720p_2mb.mp4 -r 1 frame%d.png
#             .run()
#         )
#         print(f"Frames extracted successfully to {output_dir}")
#     except ffmpeg.Error as e:
#         print(f"An error occurred: {e.stderr.decode()}")

