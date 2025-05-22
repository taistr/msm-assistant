import evdev as evdev

DEVICE_NAME = "Nintendo Switch Left Joy-Con"

joycon = None
# Find the joycon device
for path in evdev.list_devices():
    device = evdev.InputDevice(path)
    print(f"Checking: {device.name}")
    if device.name == DEVICE_NAME:
        joycon = device
        break

joycon: evdev.InputDevice | None

if joycon is None:
    raise RuntimeError("JoyCon not found")

# print the device inputs
for event in joycon.read_loop():
    parsed = evdev.categorize(event)
    print(parsed)
