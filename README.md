# Tutorial Generator
This script is a prototyp for an automated tutorial generator which can be used on any website to create tutorial videos. The voices can be generated with `PIPER` or `coqui TTS` a text to speech system. The actions are performed by `Playwright`.

## Installation
1. Create virtual environment: `python3 -m venv venv`
2. Activate environment: `source venv/bin/activate`
3. `sudo apt install espeak-ng`
4. `pip install -r requirements.txt`
5. `playwright install`

If you are using piper:
6. Install piper under `./piper`, see https://github.com/rhasspy/piper#installation. The executable should be located under `./piper/piper`. You can also set an alternative path with the `-p` argument.
7. Download a voice from https://github.com/rhasspy/piper/releases/tag/v0.0.2. When executing the script, pass the `-m` argument with the voice model path of the `.onnx` model file.

## Usage
The following steps show how to use this script.

### Playwright actions
First you need to replace the highlighted Playwright code in the `run(..)` method. You can manually implement the code or use the Playwright code generator by the command `playwright codegen [url]`. If you use the generator you can replace the example code with the generated code. Note: Only the page related code should be copied. Preferably, you should orientate on the example.

### Voice
You can insert speech between actions by calling the `page.voice(..)` function. You can wait for the end of a speech by `page.wait_for_voice()`.

### Translations
The voices can be translated into different languages by translation files which can be passed by the `-t` argument. The translation file contains a json object with key value pairs. Each key identifies a voice string and its value contains the corresponding translation. The voice string `<key>` passed to the `page.voice(<key>)` function will be replaced by the matching translation. 

### Highlight
Important elements on the page can be highlighted by a red border with the Locator's `mark(..)` function. For example, the code `page.get_by_role("button", name="Save").mark()` highlights the save button.

### Timeouts
Timeouts between actions can be set with `page.wait_for_timeout(..)`. The general timeout between actions is set to one second and can be set with the `-s` argument in milliseconds.

### Run
Finally, run the script with `python3 tutorial_generator.py -m <path-to-voice-model>`. Run `python3 tutorial_generator.py -h` to see all available arguments.