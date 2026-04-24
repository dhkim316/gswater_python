import time
from machine import UART


FRAME_HEADER = b"\x5A\xA5"
CMD_WRITE = 0x82
CMD_READ = 0x83

DEFAULT_UART_ID = 1
DEFAULT_TX_PIN = 4
DEFAULT_RX_PIN = 5
DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT = 1.0
DEFAULT_READ_POLL_MS = 10

MIN_ASCII = 32
MAX_ASCII = 255


class DgusError(RuntimeError):
    pass


class VersionInfo:
    def __init__(self, gui_version, os_version):
        self.gui_version = gui_version
        self.os_version = os_version


def words_from_bytes(data):
    if len(data) % 2 != 0:
        raise ValueError("Word data length must be even")
    return [int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data), 2)]


class DgusControl:
    def __init__(
        self,
        uart_id=DEFAULT_UART_ID,
        tx_pin=DEFAULT_TX_PIN,
        rx_pin=DEFAULT_RX_PIN,
        baudrate=DEFAULT_BAUDRATE,
        timeout=DEFAULT_TIMEOUT,
    ):
        self.uart = UART(
            uart_id,
            baudrate=baudrate,
            tx=tx_pin,
            rx=rx_pin,
            timeout=int(timeout * 1000),
        )
        self.timeout_ms = int(timeout * 1000)
        self.echo = False
        self.listener_callback = None

    def close(self):
        self.uart.deinit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def echo_enabled(self, enabled):
        self.echo = bool(enabled)

    def hmi_callback(self, callback):
        self.listener_callback = callback

    def flush(self):
        while self.uart.any():
            if not self.uart.read():
                break

    def _log_bytes(self, prefix, data):
        if self.echo and data is not None:
            print("{} {}".format(prefix, data.hex(" ")))

    def _build_frame(self, instruction, payload=b""):
        length = 1 + len(payload)
        if length > 0xFF:
            raise ValueError("Frame too large")
        return FRAME_HEADER + bytes([length, instruction]) + payload

    def _write_frame(self, instruction, payload=b""):
        frame = self._build_frame(instruction, payload)
        self.uart.write(frame)
        self._log_bytes("<<", frame)
        return frame

    def _read_exact(self, size, timeout_ms=None):
        if timeout_ms is None:
            timeout_ms = self.timeout_ms

        data = bytearray()
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while len(data) < size:
            if self.uart.any():
                chunk = self.uart.read(size - len(data))
                if chunk:
                    data.extend(chunk)
                    continue

            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                raise DgusError(
                    "Expected {} bytes, got {}".format(size, len(data))
                )
            time.sleep_ms(DEFAULT_READ_POLL_MS)
        return bytes(data)

    def _read_frame(self, timeout_ms=None):
        header = self._read_exact(2, timeout_ms)
        if header != FRAME_HEADER:
            raise DgusError("Unexpected frame header: {}".format(header.hex(" ")))

        length = self._read_exact(1, timeout_ms)[0]
        payload = self._read_exact(length, timeout_ms)
        frame = header + bytes([length]) + payload
        self._log_bytes("->>", frame)
        return payload

    def request(self, instruction, payload=b"", expect_response=True):
        self._write_frame(instruction, payload)
        if not expect_response:
            return b""
        return self._read_frame()

    def read_register(self, address, words=1):
        payload = address.to_bytes(2, "big") + bytes([words & 0xFF])
        return self.request(CMD_READ, payload)

    def write_words(self, vp_addr, words):
        payload = bytearray(vp_addr.to_bytes(2, "big"))
        for word in words:
            value = int(word)
            if value < 0 or value > 0xFFFF:
                raise ValueError("word must be between 0 and 65535")
            payload.extend(value.to_bytes(2, "big"))
        return self.request(CMD_WRITE, bytes(payload), expect_response=False)

    def write_bytes(self, vp_addr, data):
        payload = vp_addr.to_bytes(2, "big") + bytes(data)
        return self.request(CMD_WRITE, payload, expect_response=False)

    def get_hw_version(self):
        response = self.read_register(0x000F, 1)
        if len(response) < 4:
            raise DgusError("Invalid HW version response")
        return response[-1]

    def restart_hmi(self):
        payload = bytes([0x00, 0x04, 0x55, 0xAA, 0x5A, 0xA5])
        return self.request(CMD_WRITE, payload, expect_response=False)

    def set_brightness(self, brightness):
        return self.write_bytes(0x0082, bytes([brightness & 0xFF]))

    def get_brightness(self):
        response = self.read_register(0x0031, 1)
        if len(response) < 4:
            raise DgusError("Invalid brightness response")
        return response[-1]

    def set_page(self, page):
        payload = bytes([0x00, 0x84, 0x5A, 0x01, 0x00, page & 0xFF])
        return self.request(CMD_WRITE, payload, expect_response=False)

    def get_page(self):
        response = self.read_register(0x0014, 1)
        if len(response) < 4:
            raise DgusError("Invalid page response")
        return response[-1]

    def set_text(self, address, text, encoding="latin1", field_length=0):
        value = str(text)
        if field_length > 0:
            value = value[:field_length]
            if len(value) < field_length:
                value = value + (" " * (field_length - len(value)))
        payload = bytearray(value.encode(encoding))
        return self.write_bytes(address, bytes(payload))

    def set_text_unicode(self, address, text, field_length=0):
        value = str(text)
        if field_length > 0:
            value = value[:field_length]
            if len(value) < field_length:
                value = value + (" " * (field_length - len(value)))
        payload = bytearray()
        for char in value:
            code = ord(char)
            if code > 0xFFFF:
                code = ord("?")
            payload.extend(code.to_bytes(2, "big"))
        return self.write_bytes(address, bytes(payload))

    def set_vp(self, address, value):
        if value < 0 or value > 0xFFFF:
            raise ValueError("value must be between 0 and 65535")
        return self.write_words(address, [value])

    def set_vp8(self, address, value):
        if value < 0 or value > 0xFF:
            raise ValueError("value must be between 0 and 255")
        return self.write_words(address, [value])

    def beep_hmi(self, duration_ms=1000):
        if duration_ms < 0:
            raise ValueError("duration_ms must be >= 0")
        duration_units = max(0, min(0xFFFF, round(duration_ms / 8.0)))
        return self.write_words(0x00A0, [duration_units])

    def listen(self, timeout_ms=None):
        payload = self._read_frame(timeout_ms)
        if self.listener_callback:
            try:
                address = ""
                last_byte = None
                message = ""

                if len(payload) >= 3:
                    address = "{:02X}{:02X}".format(payload[1], payload[2])
                    if len(payload) > 3:
                        last_byte = payload[-1]
                        text_bytes = []
                        for value in payload[3:]:
                            if MIN_ASCII <= value < MAX_ASCII:
                                text_bytes.append(value)
                        if text_bytes:
                            message = bytes(text_bytes).decode("latin1")

                frame = FRAME_HEADER + bytes([len(payload)]) + payload
                self.listener_callback(address, last_byte, message, frame.hex(" "))
            except Exception:
                pass
        return payload

    # Compatibility aliases from the older files.
    def echoEnabled(self, enabled):
        self.echo_enabled(enabled)

    def hmiCallBack(self, callback):
        self.hmi_callback(callback)

    def flushSerial(self):
        self.flush()

    def getHWVersion(self):
        return self.get_hw_version()

    def restartHMI(self):
        return self.restart_hmi()

    def setBrightness(self, brightness):
        return self.set_brightness(brightness)

    def getBrightness(self):
        return self.get_brightness()

    def setPage(self, page):
        return self.set_page(page)

    def getPage(self):
        return self.get_page()

    def setText(self, address, text):
        return self.set_text(address, text)

    def setTextUnicode(self, address, text):
        return self.set_text_unicode(address, text)

    def setVP(self, address, value):
        return self.set_vp(address, value)

    def setVP8(self, address, value):
        return self.set_vp8(address, value)

    def beepHMI(self, duration_ms=1000):
        return self.beep_hmi(duration_ms)


DgusClient = DgusControl
DWIN = DgusControl
