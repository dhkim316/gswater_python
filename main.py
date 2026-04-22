import time

from app import run
from ble_ota_mode import run_ble_ota_mode
from button_input_pico import decode_buttons, read_hc165


def should_enter_ble_ota_mode(samples=3, pressed_threshold=2):
    pressed_count = 0
    for _ in range(samples):
        if "btn_set" in decode_buttons(read_hc165()):
            pressed_count += 1
        time.sleep_ms(20)
    return pressed_count >= pressed_threshold


if should_enter_ble_ota_mode():
    run_ble_ota_mode()
else:
    run()
