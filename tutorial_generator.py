import argparse
import datetime
import glob
import json
import shutil
import subprocess
from enum import Enum
from pathlib import Path
import wave

from moviepy.editor import *
from playwright.sync_api import Playwright, sync_playwright, Page, Locator
from TTS.api import TTS


class VoiceEngine(Enum):
    """
    Represents a text to speech system
    """
    COQUI = "coqui"
    PIPER = "piper"


tmp_dir_path = './tmp'
voice_engine = VoiceEngine.COQUI.value
coqui_tts: TTS | None = None
piper_path = './piper/piper'
translations = {}
tts_model = ''

# Used to recognize if a voice is currently active
last_voice_end_timestamp: float = 0.0

EXAMPLE_HELP_SECTION = '''
Examples:
    python3 tutorial_generator.py -v piper -p ./piper/piper -m ./voice-de-thorsten-low/de-thorsten-low.onnx -o tutorial.mp4 -s 1000 -t ./tmp
    
    python3 tutorial_generator.py -v piper -m ./voice-de-thorsten-low/de-thorsten-low.onnx
        Minimal piper example which only needs a voice model.
    python3 tutorial_generator.py -v coqui -m tts_models/de/thorsten/tacotron2-DDC
        Minimal coqui example which only needs a voice model.
        
    python3 tutorial_generator.py -v coqui -m tts_models/en/ljspeech/tacotron2-DDC -t ./example_en_translation.json
        Translation file example.
'''


def _get_audio_duration(audio_file: str) -> float:
    """
    Gets the audio duration in milliseconds
    :param audio_file: path to wav audio file
    :return: duration in ms
    """
    with wave.open(audio_file, 'rb') as f:
        return (f.getnframes() / float(f.getframerate())) * 1000


def _get_translation(key: str) -> str:
    """
    Gets the translation for the given key if translation exists
    :param key: translation key
    :return: translation if key exists. Otherwise, passed key.
    """
    global translations

    if key not in translations:
        return key

    return translations[key]


def generate_voice(self, text: str, wait=True):
    """
    Generates voice that will be played in the video at the time of the call.
    If a voice is active when this function is called, the new voice will be added after its end.

    If wait is true the page will wait until the end of the speech.

    :param self: Playwright Page object
    :param text: text to be voiced or key of translation
    :param wait: Whether actions should stop for speech duration
    :raises FileNotFoundError: If model or piper path does not exist
    """
    global last_voice_end_timestamp

    # Wait when last voice is speaking
    self.wait_for_voice()

    text = _get_translation(text)

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
    :param self: Playwright Page object
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
    """
    Initialization of the voice models
    :param model: tts model
    """
    global voice_engine, coqui_tts

    if voice_engine == VoiceEngine.COQUI.value:
        # German models:
        # tts_models/de/thorsten/tacotron2-DCA (bad quality)
        # tts_models/de/thorsten/vits (good quality)
        # tts_models/de/thorsten/tacotron2-DDC (best quality)
        coqui_tts = TTS(model)


def init_translations(translation_file: str):
    """
    Reads the passed translation file
    :param translation_file: translation file
    """
    if not translation_file:
        return

    global translations

    if not os.path.exists(translation_file):
        raise FileNotFoundError(f'Translation file {translation_file} does not exist')

    with open(translation_file) as f:
        translations = json.load(f)


def init_argparse():
    parser = argparse.ArgumentParser(
        description='Generates a tutorial from a website with speech.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLE_HELP_SECTION,
    )
    parser.add_argument('-v', '--voice-engine', type=str, dest='engine',
                        choices=[VoiceEngine.COQUI.value, VoiceEngine.PIPER.value],
                        default=VoiceEngine.COQUI.value,
                        help='The selected text-to-speech system.')
    parser.add_argument('-p', '--piper', type=str, dest='piper', default='./piper/piper',
                        help='The path to the piper executable. Default: ./piper/piper')
    parser.add_argument('-m', '--model', type=str, dest='model', required=True,
                        help='The path or name of the language model. Example: tts_models/de/thorsten/tacotron2-DDC')
    parser.add_argument('-o', '--output', type=str, dest='outputFile', default='tutorial.mp4',
                        help='The path to the output file. Default: tutorial.mp4')
    parser.add_argument('-t', '--translation-file', type=str, dest='translationPath',
                        help='The path to a file with translations for voice. If a file is configured, '
                             'the default language texts will be replaced by their translations.')
    parser.add_argument('--tmp-dir', type=str, dest='tmpDir', default='./tmp',
                        help='The path to the temporary directory. Default: ./tmp')
    parser.add_argument('-s', '--slowmo', type=int, dest='slowmo', default=1000,
                        help='Sets slow motion time in milliseconds between execution of actions. '
                             'Default: 1000.')
    return parser


def mark_element(self: Locator, timeout: float=3000):
    """
    Highlight element with a red border. The border is set by inline css.
    :param self: Locator identifying the element to highlight
    :param timeout: timeout after highlight
    :return: Locator
    """
    self.evaluate("element => element.style['border'] = '2px solid red'")
    self.wait_for(timeout=timeout)
    return self


def run(playwright: Playwright) -> None:
    parser = init_argparse()
    args = parser.parse_args()

    global tmp_dir_path, voice_engine, piper_path, tts_model
    voice_engine = args.engine
    piper_path = args.piper
    tts_model = args.model
    output_file = args.outputFile
    translation_file = args.translationPath
    tmp_dir_path = args.tmpDir
    slowmo = args.slowmo

    init_voice(tts_model)
    init_translations(translation_file)

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
    page.goto("https://studip-test.uni-osnabrueck.de/")
    page.voice("Hallo und herzlich Willkommen in Stud Ei Pi 5 Punkt 3 und diesem Video zur Fragebogenfunktion. In den Fragebögen hat sich einiges getan mit der neuen Stud Ei Pi Version und ich werde Ihnen jetzt einmal zeigen, wie die Funktion sich aktuell darstellt. Zuerst müssen Sie sich in ihr Stud Ei Pi anmelden und die Verwaltungsansicht Ihrer Veranstaltung öffnen.")
    page.get_by_label("Username:").click()
    page.get_by_label("Username:").fill("")  # TODO: Add username
    page.get_by_label("Password:").click()
    page.get_by_label("Password:").fill("")  # Todo: Add password
    page.get_by_role("button", name="Login").click()
    page.get_by_title("Meine Veranstaltungen & Einrichtungen").click()
    page.get_by_role("link", name="Test-Veranstaltung").click()  # Todo: Replace with your lecture
    page.get_by_role("link", name="Verwaltung", exact=True).click()

    page.voice("Sie sehen hier direkt auch noch den Knopf zu den Evaluationen. Dazu sei kurz gesagt, dass diese Funktion bis auf weiteres noch verfügbar sein wird in Zukunft, aber über die Fragebögen abgelöst wird.")
    page.voice("Dafür haben wir einige Fragetypen, die entsprechende Funktionen ermöglichen.", wait=False)
    page.get_by_role("link", name="Fragebögen", exact=True).click()
    page.voice("Sie sehen hier in meiner Veranstaltung, im Bereich Verwaltung, Fragebögen, bereits die Übersicht über die laufenden oder abgelaufenen Fragebögen, die ich durchgeführt habe. Sie können die Fragebögen aber auch direkt in ihrem Arbeitsplatz erstellen und von dort in alle ihre Veranstaltungen einhängen, in denen sie diesen Fragebogen nutzen möchten. Sicherlich ist aber der typische Weg, es direkt in einer Veranstaltung zu tun, das zeige ich Ihnen hier.")
    page.voice("Wenn ich jetzt einen neuen Fragebogen erstelle, dann klick ich auf Fragebogen erstellen und Aktionen und bekomme hier die Möglichkeit, einen Fragebogen für die gesamte Veranstaltung oder für einzelne Gruppen zu erstellen.", wait=False)
    page.get_by_role("link", name="Fragebogen erstellen").click()
    page.voice("Ich wähle jetzt hier die gesamte Veranstaltung.")
    page.get_by_role("link", name="Test-Veranstaltung").click()
    page.voice("Ich gebe einen Titel ein und kann hier den Start und Endzeitpunkt wählen. Dann kann ich hier auch die Teilnahme anonym machen, zum Beispiel eine wichtige Funktion für Evaluation und noch einige andere Dinge einstellen.", wait=False)
    page.get_by_label("Titel des Fragebogens *").fill("Fragebogen")
    page.get_by_label("Endzeitpunkt").click()
    page.get_by_role("link", name="31").click()
    page.get_by_label("Teilnehmende anonymisieren").check()
    page.wait_for_voice()
    page.get_by_role("link", name="Element hinzufügen").click()
    page.voice("Ich habe hier fünf verschiedene Möglichkeiten, Elemente, den Fragebogen hinzuzufügen. Einmal haben wir die Informationen, dort kann ich eine Website oder einen Video einbetten oder einen Text eingeben. Die Freitext-Frage ist auch sehr simpel, dort gebe ich eine Frage ein und die Teilnehmenden können eine Antwort in ein Freitextfeld angeben. Dann haben wir diese drei Varianten der Mehrfachauswahlfrage. Diese Scalen sind sozusagen Spezialfälle für Mehrfachauswahl, die schon vor eingestellt sind. Sie kennen diese Art von Frage-Typ mit Sicherheit.")
    page.get_by_role("button", name="Auswahlfrage").click()
    page.voice("Ich zeige Ihnen jetzt, um zu zeigen, wie die Bedienung funktioniert, einmal die Auswahlfrage, das ist die Flexibelste, aber eben auch die typischste.")
    page.voice("Hier oben kann ich jetzt meine Frage eingeben und hier unten dann meine Antwort-Optionen.", wait=False)
    page.get_by_role("textbox", name="Rich-Text-Editor, main").click()
    page.get_by_role("textbox", name="Rich-Text-Editor, main").fill("???")
    page.get_by_placeholder("Option").first.click()
    page.get_by_placeholder("Option").first.fill("1")
    page.get_by_placeholder("Option").nth(1).click()
    page.get_by_placeholder("Option").nth(1).fill("2")
    page.get_by_placeholder("Option").nth(2).click()
    page.get_by_placeholder("Option").nth(2).fill("3")
    page.get_by_placeholder("Option").nth(3).click()
    page.get_by_placeholder("Option").nth(3).fill("4")
    page.voice("Ich habe dabei die Möglichkeit, über diesen Anfasser die Optionen noch beliebig zu sortieren und zu verschieben, wie Sie sehen können. Einfach per Drag und Drop, und mit dem Mülleimer die Möglichkeit, eine Antwort-Option zu löschen und mit dem Plus kann ich beliebig viele neue hinzufügen.", wait=False)
    page.get_by_title("Sortierelement für Option 3. Drücken Sie die Tasten Pfeil-nach-oben oder Pfeil-nach-unten, um dieses Element in der Liste zu verschieben.")\
        .drag_to(page.get_by_title("Sortierelement für Option 1. Drücken Sie die Tasten Pfeil-nach-oben oder Pfeil-nach-unten, um dieses Element in der Liste zu verschieben."))
    page.get_by_role("button", name="Option löschen").nth(1).click()
    page.get_by_role("button", name="Ja").click()
    page.get_by_role("button", name="Option löschen").nth(1).click()
    page.get_by_role("button", name="Ja").click()
    page.get_by_role("button", name="Option hinzufügen").click()
    page.get_by_role("button", name="Option hinzufügen").click()
    page.get_by_placeholder("Option").nth(2).click()
    page.get_by_placeholder("Option").nth(2).fill("5")
    page.get_by_placeholder("Option").nth(3).click()
    page.get_by_placeholder("Option").nth(3).fill("6")
    page.voice("Ich kann mehrere Antworten erlauben, diese Frage zu einer Pflichtfrage machen und noch die Antworten zufällig anzeigen lassen.")
    page.voice("Jetzt kann ich also mit der Art weiteren Elementen meinen Fragebogen ausfüllen. Ich habe auch hier diese Anfasser, wie Sie sehen können, um die Reihenfolge zu verändern und im 3 Punkt Menü hier auch die Möglichkeit, die Fragen umzubenennen. Wenn ich jetzt mehrere Fragen wie hier vom gleichen Typ habe, ist das natürlich sehr praktisch.", wait=False)
    page.get_by_role("link", name="Element hinzufügen").click()
    page.get_by_role("button", name="Aktionsmenü", exact=True).click()
    page.get_by_role("link", name="Umbenennen").click()
    page.get_by_role("link", name="Internen Namen speichern").get_by_role("textbox").click()
    page.get_by_role("link", name="Internen Namen speichern").get_by_role("textbox").fill("Erste")
    page.get_by_role("button", name="Internen Namen speichern").click()
    page.voice("Ich kann sie auch kopieren oder hier direkt über diese Pfeile verschieben.", wait=False)
    page.get_by_role("button", name="Aktionsmenü", exact=True).click()
    page.get_by_role("link", name="Frage kopieren").click()
    page.get_by_role("button", name="Aktionsmenü", exact=True).nth(1).click()
    page.get_by_role("link", name="Umbenennen").click()
    page.get_by_role("link", name="Internen Namen speichern").get_by_role("textbox").click()
    page.get_by_role("link", name="Internen Namen speichern").get_by_role("textbox").fill("Zweite")
    page.get_by_role("button", name="Internen Namen speichern").click()
    page.voice("Wenn ich jetzt meinen Fragebogen speicher und den Startzeitpunkt auf sofort gestellt habe, dann startet auch sofort der Fragebogen, so wie wir hier sehen können.", wait=False)
    page.get_by_role("button", name="Speichern").click()

    page.voice("Und ich kann ihn jetzt selbst auch im 3 Punkt Menü über ausfüllen.", wait=False)
    page.get_by_role("button", name="Aktionsmenü für Fragebogen").first.click()
    page.get_by_role("link", name="Ausfüllen").click()
    page.voice("Das ist jetzt keine besonders interessante Frage. Die zweite Frage hat die gleichen Antwortmöglichkeiten.")
    page.locator("label").filter(has_text="3").first.click()
    page.locator("label").filter(has_text="5").first.click()
    page.voice("Ich habe jetzt hier auf Speichen gedrückt und dann sehen wir aber schon, wenn ich die Seite neu lade, dass wir jetzt eine Einreichung haben.", wait=False)
    page.get_by_role("button", name="Speichern").click()

    page.reload()
    page.voice("Ich kann ihn jetzt natürlich nicht noch mal ausfüllen, wenn ich jetzt hier noch mal auf ausfüllen klicke, dann wird dort der Knopf speichern fehlen.", wait=False)
    page.get_by_role("button", name="Aktionsmenü für Fragebogen").first.click()
    page.get_by_role("link", name="Ausfüllen").click()
    page.voice("Was ich allerdings machen kann, ich kann mir direkt die Auswertung schon anzeigen lassen.", wait=False)
    page.get_by_title("Schließen").click()
    page.get_by_role("button", name="Aktionsmenü für Fragebogen").first.click()
    page.get_by_role("link", name="Auswertung").click()
    page.voice("Als Lehrende in dieser Veranstaltung habe ich diese Möglichkeit, Sie hier oben direkt als Diagramm zu sehen. Und ich kann auch die Ergebnisse als CSV-Datei zur Weiterverarbeitung in einem Tabellenkalkulationsprogramm oder als PDF exportieren. Ich habe hier auch immer noch mehrere Knöpfe an verschiedenen Dialogen, die gleich funktionieren. Ich kann einmal den gesamten Fragebogen noch mal kopieren, um eine Variante zu erstellen, zum Beispiel. Oder ich kann den Bearbeitungszeitraum wählen. Ich kann aber auch den Kontext auswählen.")
    page.voice("Dafür gibt es auch hier einen Kurzbefehl.", wait=False)
    page.get_by_role("button", name="Schließen").nth(1).click()
    page.voice("Ich klicke hier auf diese Personen und kann dann die Zuweisung bearbeiten. Also auf welchen Bereichen in Stud Ei Pi dieser Fragebogen erscheinen soll.", wait=False)
    page.get_by_role("link", name="Zuweisungen bearbeiten").first.click()
    page.get_by_label("Auf der persönlichen Profilseite").check()
    page.voice("So, ich habe jetzt hier meine persönliche Profilseite ausgewählt und kann jetzt aus meinen Veranstaltungen hier eine weitere Veranstaltung auswählen. Hier kann ich aber auch teilnehmenden Gruppen auswählen und entsprechend auch wieder Veranstaltungen entfernen. Das mache ich jetzt nicht.", wait=False)
    page.get_by_placeholder("Veranstaltung suchen").click()
    page.get_by_placeholder("Veranstaltung suchen").fill("test")
    page.get_by_role("dialog", name="Bereiche für Fragebogen: Fragebogen").get_by_text("LTI-Test (SoSe 2023)").click()  # Todo: Replace with other lecture
    page.voice("Und wenn wir jetzt die Seite neu geladen haben, sehen wir auch gleich, dass die Profilseite und das zweite Testseminar hier aufgetaucht sind.", wait=False)
    page.get_by_role("button", name="Speichern").click()
    page.wait_for_timeout(1000)  # Wait some time before reload page to prevent errors
    page.reload()
    page.voice("Auch dort ist jetzt dieser Fragebogen zu sehen und kann von den Teilnehmenden ausgefüllt werden. Ich kann natürlich den Fragebogen nicht mehr bearbeiten, wenn schon eine Einreichung vorhanden ist. Deswegen ist dieses Symbol ausgegraut. Ist es blau, so wie beim anderen, dann weil noch keine Einreichung vorhanden ist. Dann kann ich den Fragebogen hier auch ganz einfach bearbeiten.")

    # page.voice("Zuletzt zeige ich Ihnen noch einmal kurz die Fragebögen im Arbeitsplatz.")
    # page.get_by_role("link", name="Arbeitsplatz").click()
    # page.voice("Im Arbeitsplatz haben die Fragebögen auch einen eigenen Bereich und dort finden Sie alle Fragebögen, die Sie in Stud Ei Pi durchgeführt haben, aktuell oder in der Vergangenheit und wo diese eingehängt sind. Sie können hier genau das gleiche tun, wie wir das vorhin schon gesehen haben.", wait=False)
    # page.get_by_role("link", name="Fragebögen Zentrale Sammlung Ihrer Fragebögen").click()
    # page.get_by_role("button", name="Aktionsmenü für Fragebogen").first.click()
    # page.locator(".action-menu-wrapper > .action-menu-icon").click()
    # page.voice("So weit in Kürze ein Überblick über die Fragebogenfunktionen in Stud Ei Pi 5 Punkt 3. Ich wünsche Ihnen weiterhin viel Erfolg mit Ihrer Lehre und mit den Fragebögen in Stud Ei Pi.")
    # ---------------------

    # end_datetime = datetime.datetime.now()

    context.close()
    browser.close()

    _make_video(start_datetime, output_file)

    shutil.rmtree(tmp_dir_path)


with sync_playwright() as playwright:
    run(playwright)
