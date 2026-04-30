import time

try:
    import _thread
except ImportError:
    _thread = None

from rf_packet_parser_pico import extract_valid_frame, parse_frame


MODE_LEVEL = "level"
MODE_FLOW = "flow"


class _NullLock:
    def acquire(self):
        return True

    def release(self):
        return None


def _sleep_ms(ms):
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(ms)
    else:
        time.sleep(ms / 1000.0)


def parse_flow_response(raw_packet):
    if not raw_packet or len(raw_packet) < 8:
        return None

    start = len(raw_packet) - 8
    while start >= 0:
        frame = raw_packet[start:start + 8]
        payload = frame[:7]
        checksum = frame[7]

        if payload[:1] == b"{" and payload[6:7] == b"}":
            digits = payload[1:6]
            if all(48 <= value <= 57 for value in digits):
                if (sum(payload) & 0xFF) == checksum:
                    return bytes(digits).decode("ascii")
        start -= 1

    return None


class RFReceiveThread:
    def __init__(self, rf, poll_ms=10, max_buffer_size=96):
        self.rf = rf
        self.poll_ms = poll_ms
        self.max_buffer_size = max_buffer_size
        self.supported = _thread is not None
        self.lock = _thread.allocate_lock() if self.supported else _NullLock()
        self.running = False
        self.started = False
        self.mode = None
        self.waiting = False
        self.buffer = bytearray()
        self.result = None

    def start(self):
        if not self.supported or self.started:
            return False
        self.running = True
        self.started = True
        _thread.start_new_thread(self._run, ())
        return True

    def stop(self):
        self.running = False

    def begin_level(self):
        self._begin(MODE_LEVEL)

    def begin_flow(self):
        self._begin(MODE_FLOW)

    def cancel(self):
        self.lock.acquire()
        try:
            self.waiting = False
            self.mode = None
            self.buffer = bytearray()
            self.result = None
        finally:
            self.lock.release()

    def pop_result(self):
        self.lock.acquire()
        try:
            result = self.result
            self.result = None
            return result
        finally:
            self.lock.release()

    def _begin(self, mode):
        self.lock.acquire()
        try:
            self.mode = mode
            self.waiting = True
            self.buffer = bytearray()
            self.result = None
        finally:
            self.lock.release()

    def _run(self):
        while self.running:
            try:
                self.service_once()
            except Exception as exc:
                print("RF receive thread error: {}".format(exc))
            _sleep_ms(self.poll_ms)

    def service_once(self):
        self.lock.acquire()
        try:
            waiting = self.waiting
            mode = self.mode
        finally:
            self.lock.release()

        if not waiting:
            return

        chunk = self.rf.receive_available()
        if not chunk:
            return

        self.lock.acquire()
        try:
            if not self.waiting:
                return

            self.buffer.extend(chunk)
            overflow = len(self.buffer) - self.max_buffer_size
            if overflow > 0:
                self.buffer = self.buffer[overflow:]

            result = self._parse_result(self.mode, self.buffer)
            if result:
                self.result = result
                self.waiting = False
                self.mode = None
                self.buffer = bytearray()
        finally:
            self.lock.release()

    def _parse_result(self, mode, buffer):
        if mode == MODE_LEVEL:
            frame = extract_valid_frame(buffer)
            if not frame:
                return None
            return {
                "mode": MODE_LEVEL,
                "raw": bytes(buffer),
                "parsed": parse_frame(frame),
            }

        if mode == MODE_FLOW:
            pulse = parse_flow_response(buffer)
            if pulse is None:
                return None
            return {
                "mode": MODE_FLOW,
                "raw": bytes(buffer),
                "flow_pulse": pulse,
            }

        return None
