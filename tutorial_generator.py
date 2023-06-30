import argparse
import datetime
import glob
import shutil
import subprocess
from enum import Enum
from pathlib import Path
import wave

from moviepy.editor import *
from playwright.sync_api import Playwright, sync_playwright, Page, Locator
from TTS.api import TTS


class VoiceEngine(Enum):
    COQUI = "coqui"
    PIPER = "piper"


tmp_dir_path = './tmp'
voice_engine = VoiceEngine.COQUI.value
coqui_tts: TTS | None = None
piper_path = './piper/piper'
tts_model = ''

# Used to recognize if a voice is currently active
last_voice_end_timestamp: float = 0.0

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


def generate_voice(self, text: str, wait=True):
    """
    Generates an audio file that will be played in the video at the time of the call.

    If wait is true the page will wait for the duration of the speech.

    :param page: Playwright Page object
    :param wait: Whether actions should stop for speech duration
    :param text: text to be voiced
    :raises FileNotFoundError: If model or piper path does not exist
    """
    global last_voice_end_timestamp

    # Wait when last voice is speaking
    self.wait_for_voice()

    voice_start_timestamp = datetime.datetime.now().timestamp()
    output_file = os.path.join(tmp_dir_path, f'{round(voice_start_timestamp)}.wav')

    start_process_datetime = datetime.datetime.now()
    if voice_engine == VoiceEngine.COQUI.value:
        coqui_tts.tts_to_file(text=text, file_path=output_file)
    else:
        # Ensure model exists
        if not os.path.exists(tts_model):
            raise FileNotFoundError(f'Model path {tts_model} does not exist')

        # Ensure piper exists
        if not os.path.exists(piper_path):
            raise FileNotFoundError(f'Piper executable {piper_path} does not exist')

        subprocess.run(
            [piper_path, '--model', tts_model, '--output_file', output_file],
            input=str.encode(text)
        )

    end_process_datetime = datetime.datetime.now()
    processing_time = end_process_datetime - start_process_datetime

    voice_duration_ms = _get_audio_duration(output_file)
    # Store last voice end time
    last_voice_end_timestamp = voice_start_timestamp + voice_duration_ms / 1000

    # Add time out to page with the duration of the speech
    wait_time = voice_duration_ms - processing_time.seconds * 1000
    if wait and wait_time > 0.0:
        self.wait_for_timeout(wait_time)


def wait_for_voice(self):
    """
    Waits when the last voice is speaking until its end time
    """
    last_voice_remaining_duration_sec = last_voice_end_timestamp - datetime.datetime.now().timestamp()
    if last_voice_remaining_duration_sec > 0.0:
        self.wait_for_timeout(last_voice_remaining_duration_sec * 1000)


def _make_video(start_datetime: datetime, output_file: str):
    # Collect all voice files
    voice_files = glob.glob(f'{tmp_dir_path}/*.wav')

    # Add all voices to video
    video_file = glob.glob(f'{tmp_dir_path}/*.webm')[0]
    video_clip = VideoFileClip(video_file)

    voice_clips = []
    for voice_file in voice_files:
        file_timestamp = int(Path(voice_file).stem)
        start_time = file_timestamp - start_datetime.timestamp()
        voice_clips.append(AudioFileClip(voice_file).set_start(start_time))

    if voice_clips:
        video_clip.audio = CompositeAudioClip(voice_clips)

    # Save created video
    video_clip.write_videofile(output_file, codec="libx264", audio_codec="aac")


def init_voice(model: str):
    global voice_engine, coqui_tts

    if voice_engine == VoiceEngine.COQUI.value:
        # German models:
        # tts_models/de/thorsten/tacotron2-DCA (bad quality)
        # tts_models/de/thorsten/vits (good quality)
        # tts_models/de/thorsten/tacotron2-DDC (best quality)
        coqui_tts = TTS(model)


def init_argparse():
    parser = argparse.ArgumentParser(
        description='Generates a tutorial from a website with speech.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLE_HELP_SECTION,
    )
    parser.add_argument('-v', '--voice-engine', type=str, dest='engine', default=VoiceEngine.COQUI.value,
                        help=f'The selected text-to-speech system. Values: {VoiceEngine.COQUI.value} (default), '
                             f'{VoiceEngine.PIPER.value}')
    parser.add_argument('-p', '--piper', type=str, dest='piper', default='./piper/piper',
                        help='The path to the piper executable. Default: ./piper/piper')
    parser.add_argument('-m', '--model', type=str, dest='model', required=True,
                        help='The path or name of the language model. Example: tts_models/de/thorsten/tacotron2-DDC')
    parser.add_argument('-o', '--output', type=str, dest='outputFile', default='tutorial.mp4',
                        help='The path to the output file. Default: tutorial.mp4')
    parser.add_argument('-t', '--tmp-dir', type=str, dest='tmpDir', default='./tmp',
                        help='The path to the temporary directory. Default: ./tmp')
    parser.add_argument('-s', '--slowmo', type=int, dest='slowmo', default=1000,
                        help='Sets slow motion time in milliseconds between execution of actions. '
                             'Default: 1000.')
    return parser


def mark_element(self: Locator, timeout: float=3000):
    self.evaluate("element => element.style['border'] = '2px solid red'")
    self.wait_for(timeout=timeout)
    return self


def run(playwright: Playwright) -> None:
    parser = init_argparse()
    args = parser.parse_args()

    global tmp_dir_path, voice_engine, piper_path, tts_model
    tmp_dir_path = args.tmpDir
    voice_engine = args.engine
    piper_path = args.piper
    tts_model = args.model
    output_file = args.outputFile
    slowmo = args.slowmo

    init_voice(tts_model)

    if os.path.exists(tmp_dir_path):
        shutil.rmtree(tmp_dir_path)

    os.mkdir(tmp_dir_path)

    browser = playwright.chromium.launch(
        headless=False,
        slow_mo=slowmo  # Slow down execution speed
    )
    context = browser.new_context(
        record_video_dir=tmp_dir_path,
        viewport={'width': 1920, 'height': 1080},
        record_video_size={'width': 1920, 'height': 1080}
    )

    start_datetime = datetime.datetime.now()

    # TODO: Move to subclass
    Locator.mark = mark_element
    Page.voice = generate_voice
    Page.wait_for_voice = wait_for_voice

    # Replace example code below with your playwright code.
    # You can simply generate code with the playwright generator in the shell
    # with the command: `playwright codegen [url]`
    # ---------------------
    page = context.new_page()
    page.goto("http://localhost/studip/")
    page.voice("Dieses Tutorial zeigt, wie LTI Tools in Stud IP global konfiguriert werden können und diese in Courseware eingebunden werden.")

    page.voice("Zuerst melden sie sich mit ihren Zugangsdaten als Root-Nutzer in ihr Stud IP ein.", wait=False)
    page.get_by_role("link", name="Login for registered users").click()
    page.get_by_label("Username:").click()
    page.get_by_label("Username:").fill("root@studip")
    page.get_by_label("Username:").press("Tab")
    page.get_by_label("Password:").fill("testing123")
    page.get_by_role("button", name="Login").click()

    page.get_by_title("Zu Ihrer Administrationsseite").mark()
    page.voice("Öffnen Sie anschließend die Administrationsseite")
    page.get_by_title("Zu Ihrer Administrationsseite").click()
    page.get_by_role("link", name="System").mark()
    page.voice("Wählen sie hier den Reiter System")
    page.get_by_role("link", name="System").click()
    page.get_by_role("link", name="LTI-Tools").mark()
    page.voice("Klicken Sie links in der Navigation auf LTI-Tools")
    page.get_by_role("link", name="LTI-Tools").click()
    page.get_by_role("link", name="Neues LTI-Tool registrieren").mark(timeout=0)
    page.voice("Um ein neues LTI-Tool zu erstellen, wählen sie die Aktion 'Neues LTI Tool registrieren'")
    page.get_by_role("link", name="Neues LTI-Tool registrieren").click()
    page.voice("In diesem Dialog-Fenster können Sie alle relevanten Einstellungen ihres LTI Tools vornehmen."
               " Dazu zählen unter anderem der Name des Tools, seine URL und seine Schlüssel."
               " Als Beispiel wird ein JupyterHub-Tool konfiguriert.")
    page.get_by_label("Name der Anwendung").fill("JupyterHub")
    page.get_by_label("URL der Anwendung").click()
    page.get_by_label("URL der Anwendung").fill("https://localhost/jupyterhub/hub/lti/launch")
    page.get_by_label("Consumer-Key").click()
    page.get_by_label("Consumer-Key").fill("key")
    page.get_by_label("Consumer-Secret").click()
    page.get_by_label("Consumer-Secret").fill("secret")
    page.get_by_label("Eingabe einer abweichenden URL im Kurs erlauben").check()
    page.get_by_label("Zusätzliche LTI-Parameter").click()
    page.voice("Abschließend speichern sie das Tool mit der Schaltfläche.")
    page.get_by_role("button", name="Speichern").click()

    page.voice("Das Tool ist nun konfiguriert und kann in Courseware genutzt werden. "
               "Als Beispiel öffnen Sie die Courseware in ihrem Arbeitsbereich.")
    page.get_by_role("link", name="Arbeitsplatz").mark().click()
    page.voice("Erstellen Sie exemplarisch ein neues Lehrmaterial und öffnen sie dieses.", wait=False)
    page.get_by_role("link", name="Courseware Erstellen und Sammeln von Lernmaterialien").click()
    page.get_by_role("button", name="Lernmaterial hinzufügen").click()
    page.get_by_label("Titel des Lernmaterials*").click()
    page.get_by_label("Titel des Lernmaterials*").fill("JupyterHub-Test")
    page.get_by_label("Beschreibung*").click()
    page.get_by_label("Beschreibung*").fill("Ich bin eine JupyterHub-Test Courseware")
    page.get_by_role("button", name="Erstellen").click()
    page.get_by_role("link", name="JupyterHub-Test Ich bin eine JupyterHub-Test Courseware").click()

    page.voice("Legen sie nun den ersten Inhalt mit der entsprechenden Schaltfläche an.")
    page.get_by_role("button", name="Ersten Inhalt erstellen").mark().click()
    page.get_by_role("button", name="Block zu diesem Abschnitt hinzufügen").mark()
    page.voice("Als nächstes fügen wir den LTI-Block hinzu. Dazu klicken Sie auf die Schaltfläche 'Block zu diesem Abschnitt hinzufügen'")
    page.get_by_role("button", name="Block zu diesem Abschnitt hinzufügen").click()
    page.voice("Suchen sie nach dem LTI-Block und wählen diesen aus.")
    page.get_by_role("tabpanel", name="Blöcke").get_by_role("textbox").fill("lti")
    page.get_by_role("link", name="LTI Einbinden eines externen Tools.").mark().click()
    page.get_by_role("button", name="schließen").click()
    page.voice("Sie sehen jetzt die Bearbeitenansicht des Blocks. Auf dieser können sie den Namen des Blocks eingeben und"
               " das LTI-Tool auswählen.")
    page.get_by_label("Titel").click()
    page.get_by_label("Titel").fill("JupyterHub")
    page.voice("Nachdem sie den Block fertig konfiguriert haben, können sie diesen mit der Schaltfläche abspeichern.")
    page.locator("section").filter(
        has_text="Bearbeiten Grunddaten Zusätzliche Einstellungen Titel Auswahl des externen Tools").get_by_role(
        "button", name="Speichern").click()
    page.get_by_role("button", name="Aktionsmenü für LTI").click()
    page.voice("Das Tool wird jetzt angezeigt und kann in ihrer Courseware genutzt werden")

    page.voice("Wenn sie zurück auf die Bearbeitenansicht des Blocks gehen, können sie sehen,"
               " dass sie bei der Auswahl des Tools auch ein eigenes Tool konfigurieren können.", wait=False)
    page.get_by_role("link", name="Block bearbeiten").click()
    page.get_by_role("combobox", name="Auswahl des externen Tools").select_option("0")
    page.voice("Sie haben jetzt gelernt, wie sie ein LTI-Tool global in Stud I P konfigurieren und dieses in"
               " Courseware nutzen können.")
    page.get_by_role("list", name="Dritte Navigationsebene").get_by_role("link", name="Übersicht").click()
    page.get_by_role("button", name="Aktionsmenü für JupyterHub-Test").click()
    page.get_by_role("link", name="Löschen").click()
    page.get_by_role("button", name="Ja").click()
    # ---------------------

    # end_datetime = datetime.datetime.now()

    context.close()
    browser.close()

    _make_video(start_datetime, output_file)

    shutil.rmtree(tmp_dir_path)


with sync_playwright() as playwright:
    run(playwright)
