from PIL import Image
import cv2
import numpy as np
import asyncio
from pyscript import document
from pyodide.ffi import create_proxy

# takes gif/video input and plays back with braille and fullblock ascii.

ASCII_CHARS = ["█","▓","▒","░","⣿","⣾","⣽","⣻","⣺","⣶","⣴","⣤","⣀","⠿","⠾","⠼","⠸","⠰","⠠","⠀"]

# Global buffer to store converted frames
frame_buffer = []
current_playback_task = None

# HTML color styling - all white for better visibility
def get_color_for_brightness(pixel):
    # Using different white/light gray shades for subtle variation
    if pixel < 36:
        return '#ffffff'
    elif pixel < 72:
        return '#ffffff'
    elif pixel < 108:
        return '#ffffff'
    elif pixel < 144:
        return '#ffffff'
    elif pixel < 180:
        return '#ffffff'
    elif pixel < 216:
        return '#ffffff'
    else:
        return '#ffffff'

def resize_image(image, new_width=80):
    width, height = image.size
    ratio = height / width
    new_height = int(new_width * ratio)
    resized_image = image.resize((new_width, new_height))
    return resized_image

def resize_frame(frame, new_width=80):
    """Resize numpy array frame from OpenCV"""
    height, width = frame.shape[:2]
    ratio = height / width
    new_height = int(new_width * ratio)
    resized = cv2.resize(frame, (new_width, new_height))
    return resized

def monochrome(image):
    grayscale_image = image.convert("L")
    return grayscale_image

def frame_to_grayscale(frame):
    """Convert OpenCV frame to grayscale"""
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

def pixels_to_ascii(image):
    pixels = image.getdata()
    characters = "".join([ASCII_CHARS[pixel//15] for pixel in pixels])
    return (characters, list(pixels))

def array_to_ascii(gray_array):
    """Convert numpy grayscale array to ASCII"""
    pixels = gray_array.flatten()
    characters = "".join([ASCII_CHARS[pixel//15] for pixel in pixels])
    return (characters, list(pixels))

def colorize_ascii_html(characters, pixels, width):
    """Convert ASCII art to HTML - all white text for better visibility"""
    html_lines = []
    for i in range(0, len(characters), width):
        line = characters[i:i+width]
        html_lines.append(line)
    return "\n".join(html_lines)

async def convert_gif_to_buffer(image, new_width=80):
    """Convert all GIF frames to ASCII and store in buffer"""
    global frame_buffer
    frame_buffer = []

    output_elem = document.querySelector("#output")

    try:
        frame_count = image.n_frames

        for frame_index in range(frame_count):
            image.seek(frame_index)
            frame = image.copy()

            # Convert frame to ASCII
            new_image_data, pixel_values = pixels_to_ascii(monochrome(resize_image(frame, new_width)))
            colored_output = colorize_ascii_html(new_image_data, pixel_values, new_width)

            frame_buffer.append(colored_output)

            # Update progress
            output_elem.innerHTML = f"Converting... {frame_index + 1}/{frame_count} frames"
            await asyncio.sleep(0)  # Allow UI to update

        output_elem.innerHTML = f"Conversion complete! {len(frame_buffer)} frames ready. Starting playback..."
        await asyncio.sleep(0.5)

    except Exception as e:
        output_elem.innerHTML = f"Error converting GIF: {str(e)}"
        return False

    return True

async def convert_video_to_buffer(file_path, new_width=80):
    """Convert all video frames to ASCII and store in buffer"""
    global frame_buffer
    frame_buffer = []

    output_elem = document.querySelector("#output")

    try:
        # Open video file
        cap = cv2.VideoCapture(file_path)

        if not cap.isOpened():
            output_elem.innerHTML = f"Error: Could not open video file"
            return False

        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Read and convert all frames
        frame_index = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Resize and convert to grayscale
            resized = resize_frame(frame, new_width)
            gray = frame_to_grayscale(resized)

            # Convert to ASCII
            ascii_chars, pixel_values = array_to_ascii(gray)
            colored_output = colorize_ascii_html(ascii_chars, pixel_values, new_width)

            frame_buffer.append(colored_output)

            # Update progress
            frame_index += 1
            if frame_index % 10 == 0:  # Update every 10 frames to avoid too many DOM updates
                output_elem.innerHTML = f"Converting... {frame_index}/{total_frames} frames"
                await asyncio.sleep(0)  # Allow UI to update

        cap.release()

        if not frame_buffer:
            output_elem.innerHTML = "Error: No frames found in video"
            return False

        output_elem.innerHTML = f"Conversion complete! {len(frame_buffer)} frames ready. Starting playback..."
        await asyncio.sleep(0.5)

    except Exception as e:
        output_elem.innerHTML = f"Error converting video: {str(e)}"
        return False

    return True

async def play_from_buffer(fps=20):
    global frame_buffer

    output_elem = document.querySelector("#output")
    frame_delay = 1.0 / fps

    if not frame_buffer:
        output_elem.textContent = "No frames to play"
        return

    # Animation loop
    frame_index = 0
    while True:
        # Use textContent instead of innerHTML for faster rendering
        output_elem.textContent = frame_buffer[frame_index]

        # Move to next frame
        frame_index = (frame_index + 1) % len(frame_buffer)

        # Wait before next frame
        await asyncio.sleep(frame_delay)

async def start_conversion(*args, **kwargs):
    global frame_buffer, current_playback_task

    from js import window
    import io
    width_input = document.querySelector("#widthInput")
    output_elem = document.querySelector("#output")
    convert_btn = document.querySelector("#startBtn")

    width = int(width_input.value) if width_input.value else 80

    if not hasattr(window, 'selectedVideoFile') or window.selectedVideoFile is None:
        output_elem.innerHTML = "Please select a file first"
        return
    if current_playback_task:
        current_playback_task.cancel()

    convert_btn.disabled = True
    convert_btn.textContent = "Converting..."

    file = window.selectedVideoFile
    file_name = file.name
    output_elem.innerHTML = "Loading file..."
    file_array = await file.arrayBuffer()
    file_bytes = file_array.to_py().tobytes()

    file_ext = file_name.lower().split('.')[-1]

    success = False
    fps = 20  # Default FPS

    if file_ext == 'gif':
        # Load GIF from bytes using PIL
        image = Image.open(io.BytesIO(file_bytes))
        success = await convert_gif_to_buffer(image, width)
        fps = 20  # GIFs typically play at 20 FPS
    elif file_ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
        # For video, we need to save to a temp file for OpenCV
        temp_path = f"/tmp/{file_name}"
        with open(temp_path, 'wb') as f:
            f.write(file_bytes)
        cap = cv2.VideoCapture(temp_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        fps *= 2
        if fps <= 0:
            fps = 60
        cap.release()
        success = await convert_video_to_buffer(temp_path, width)
    else:
        output_elem.innerHTML = f"Unsupported file format: .{file_ext}<br>Supported: .gif, .mp4, .mov, .avi, .mkv, .webm"

    convert_btn.disabled = False
    convert_btn.textContent = "Convert"
    if success:
        current_playback_task = asyncio.create_task(play_from_buffer(fps))

start_button = document.querySelector("#startBtn")
start_button.addEventListener("click", create_proxy(start_conversion))
