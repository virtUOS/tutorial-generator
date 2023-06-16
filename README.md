# Tutorial Generator
This script are a prototyp for an automated tutorial generator which can be used on any website to create tutorial videos. The voices are generated with `PIPER` a text to speech system. The actions are performed by `Playwright`.

## Installation
1. Install piper under `./piper`, see https://github.com/rhasspy/piper#installation. The executable should be located under `./piper/piper`.
2. Download a voice from https://github.com/rhasspy/piper/releases/tag/v0.0.2. Then configure variable `model_path` in the script to point to the `.onnx` voice model file.
3. `pip install -r requirements.txt `
4. `playwright install`

## Usage
The following steps show how to use this script.

### Playwright actions
First you need to replace the highlighted Playwright code in the `run(..)` method. You can manually implement the code or use the Playwright code generator by the command `playwright codegen [url]`. If you use the generator you can replace the example code with the generated code. Note: Only the page related code should be copied. Preferably, you should orientate on the example.

### Voice
You can insert speech between actions by calling the `generate_voice` function.

### Timeouts
Timeouts between actions can be set with `page.wait_for_timeout(..)`. The general timeout between actions is set to one second and can be adjusted in the `launch(..)` call with the `slow_mo` parameter. Example for timeout of three seconds:
```python
browser = playwright.chromium.launch(
    headless=False,
    slow_mo=3000 
)
```

### Run
Finally, run the script with `python3 tutorial_generator.py`.