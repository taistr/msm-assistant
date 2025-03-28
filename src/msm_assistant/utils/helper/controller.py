import platform

class JoyCon:
    def __init__(right: bool = True):
        if platform.system() != "linux":
            raise OSError("JoyCon control is only supported on linux")

        pass
