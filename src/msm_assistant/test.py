from importlib.resources import as_file, files

wav_resource = files("msm_assistant.assets").joinpath("airplane_ding.wav")
with as_file(wav_resource) as path:
    # path is a pathlib.Path you can hand to sounddevice, pydub, etc.
    print(path)
