import datetime
import glob
import shutil
import subprocess
from pathlib import Path
import wave

from moviepy.editor import *
from playwright.sync_api import Playwright, sync_playwright

tmp_dir_path = './tmp'
piper_path = './piper/piper'
model_path = './voice-de-thorsten-low/de-thorsten-low.onnx'


def _get_audio_duration(audio_file: str) -> float:
    """
    Gets the audio duration in milliseconds
    :param audio_file: path to wav audio file
    :return: duration in ms
    """
    with wave.open(audio_file, 'rb') as f:
        return (f.getnframes() / float(f.getframerate())) * 1000


def generate_voice(text: str, page, wait=True):
    """
    Generates an audio file that will be played in the video at the time of the call.

    If wait is true the page will wait for the duration of the speech.

    :param page: Playwright Page object
    :param wait: Whether actions should stop for speech duration
    :param text: text to be voiced
    """
    output_file = os.path.join(tmp_dir_path, f'{round(datetime.datetime.now().timestamp())}.wav')
    subprocess.run(
        [piper_path, '--model', model_path, '--output_file', output_file],
        input=str.encode(text)
    )

    # Add time out to page with the duration of the speech
    if wait:
        page.wait_for_timeout(_get_audio_duration(output_file))


def _make_video(start_datetime):
    # Collect all voice files
    voice_files = glob.glob(f'{tmp_dir_path}/*.wav')
    print(voice_files)

    # Add all voices to video
    video_file = glob.glob(f'{tmp_dir_path}/*.webm')[0]
    video_clip = VideoFileClip(video_file)

    voice_clips = []
    for voice_file in voice_files:
        file_timestamp = int(Path(voice_file).stem)
        start_time = file_timestamp - start_datetime.timestamp()
        voice_clips.append(AudioFileClip(voice_file).set_start(start_time))

    video_clip.audio = CompositeAudioClip(voice_clips)

    # Save created video
    video_clip.write_videofile('tutorial.mp4', codec="libx264", audio_codec="aac")


def run(playwright: Playwright) -> None:
    if os.path.exists(tmp_dir_path):
        shutil.rmtree(tmp_dir_path)

    os.mkdir(tmp_dir_path)

    browser = playwright.chromium.launch(
        headless=False,
        slow_mo=1000  # Slow down execution speed
    )
    context = browser.new_context(
        record_video_dir=tmp_dir_path,
        viewport={'width': 1280, 'height': 720},
        record_video_size={'width': 1280, 'height': 720}
    )

    start_datetime = datetime.datetime.now()


    # Replace example code below with your playwright code.
    # You can simply generate code with the playwright generator in the shell with the command: `playwright codegen [url]`
    # ---------------------
    page = context.new_page()
    page.goto("http://localhost/studip/")
    generate_voice("Zuerst müssen Sie sich mit ihren Anmeldedaten bei Stud.IP anmelden.", page)
    page.get_by_role("link", name="Login for registered users").click()
    page.get_by_label("Username:").click()
    page.get_by_label("Username:").fill("root@studip")
    page.get_by_label("Username:").press("Tab")
    page.get_by_label("Password:").fill("testing")
    page.get_by_label("Password:").press("Enter")
    generate_voice("Danach öffnen sie den Arbeitsplatz.", page)
    page.get_by_role("link", name="Arbeitsplatz", exact=True).click()
    page.get_by_role("link", name="Courseware Erstellen und Sammeln von Lernmaterialien").click()
    # ---------------------

    # end_datetime = datetime.datetime.now()

    context.close()
    browser.close()

    _make_video(start_datetime)

    shutil.rmtree(tmp_dir_path)


with sync_playwright() as playwright:
    run(playwright)
