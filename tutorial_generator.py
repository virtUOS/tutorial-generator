import argparse
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
model_path = ''

EXAMPLE_HELP_SECTION = '''
Examples:
    python3 tutorial_generator.py -p ./piper/piper -m ./voice-de-thorsten-low/de-thorsten-low.onnx -o tutorial.mp4 -s 1000 -t ./tmp

    python3 tutorial_generator.py -m ./voice-de-thorsten-low/de-thorsten-low.onnx
        Minimal example which only needs a voice model.
'''


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
    :raises FileNotFoundError: If model or piper path does not exist
    """
    # Ensure model exists
    if not os.path.exists(model_path):
        raise FileNotFoundError(f'Model path {model_path} does not exist')

    # Ensure piper exists
    if not os.path.exists(piper_path):
        raise FileNotFoundError(f'Model path {piper_path} does not exist')

    output_file = os.path.join(tmp_dir_path, f'{round(datetime.datetime.now().timestamp())}.wav')
    subprocess.run(
        [piper_path, '--model', model_path, '--output_file', output_file],
        input=str.encode(text)
    )

    # Add time out to page with the duration of the speech
    if wait:
        page.wait_for_timeout(_get_audio_duration(output_file))


def _make_video(start_datetime, output_file):
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
    video_clip.write_videofile(output_file, codec="libx264", audio_codec="aac")


def init_argparse():
    parser = argparse.ArgumentParser(
        description='Generates a tutorial from a website with speech.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLE_HELP_SECTION,
    )
    parser.add_argument('-p', '--piper', type=str, dest='piper', default='./piper/piper',
                        help='The path to the piper executable. Default: ./piper/piper')
    parser.add_argument('-m', '--model', type=str, dest='model', required=True,
                        help='The path to the piper language model. Example: ./voice-de-thorsten-low/de-thorsten-low.onnx')
    parser.add_argument('-o', '--output', type=str, dest='outputFile', default='tutorial.mp4',
                        help='The path to the output file. Default: tutorial.mp4')
    parser.add_argument('-t', '--tmp-dir', type=str, dest='tmpDir', default='./tmp',
                        help='The path to the temporary directory. Default: ./tmp')
    parser.add_argument('-s', '--slowmo', type=int, dest='slowmo', default=1000,
                        help='Sets slow motion time in milliseconds between execution of actions. '
                             'Default: 1000.')
    return parser


def run(playwright: Playwright) -> None:
    parser = init_argparse()
    args = parser.parse_args()

    global tmp_dir_path, piper_path, model_path
    tmp_dir_path = args.tmpDir
    piper_path = args.piper
    model_path = args.model
    output_file = args.outputFile
    slowmo = args.slowmo

    if os.path.exists(tmp_dir_path):
        shutil.rmtree(tmp_dir_path)

    os.mkdir(tmp_dir_path)

    browser = playwright.chromium.launch(
        headless=False,
        slow_mo=slowmo  # Slow down execution speed
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

    _make_video(start_datetime, output_file)

    shutil.rmtree(tmp_dir_path)


with sync_playwright() as playwright:
    run(playwright)
