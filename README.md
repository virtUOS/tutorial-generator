# Tutorial Generator
This script is a prototyp for an automated tutorial generator which can be used on any website to create tutorial videos. The voices are generated with `PIPER` a text to speech system. The actions are performed by `Playwright`.

## Installation
1. Install piper under `./piper`, see https://github.com/rhasspy/piper#installation. The executable should be located under `./piper/piper`. You can also set an alternative path with the `-p` argument.
2. Download a voice from https://github.com/rhasspy/piper/releases/tag/v0.0.2. When executing the script, pass the `-m` argument with the voice model path of the `.onnx` model file.
3. `pip install -r requirements.txt`
4. `playwright install`

## Usage
The following steps show how to use this script.

### Playwright actions
First you need to replace the highlighted Playwright code in the `run(..)` method. You can manually implement the code or use the Playwright code generator by the command `playwright codegen [url]`. If you use the generator you can replace the example code with the generated code. Note: Only the page related code should be copied. Preferably, you should orientate on the example.

### Voice
You can insert speech between actions by calling the `generate_voice` function.

### Timeouts
Timeouts between actions can be set with `page.wait_for_timeout(..)`. The general timeout between actions is set to one second and can be set with the `-s` argument in milliseconds.

### Run
Finally, run the script with `python3 tutorial_generator.py -m <path-to-voice-model>`. Run `python3 tutorial_generator.py -h` to see all available arguments.