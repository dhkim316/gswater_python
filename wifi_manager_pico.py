import time

try:
    import network
except ImportError:
    network = None


class WifiStationManager:
    def __init__(
        self,
        reconnect_delay_ms=5000,
        connect_timeout_ms=20000,
    ):
        self.reconnect_delay_ms = reconnect_delay_ms
        self.connect_timeout_ms = connect_timeout_ms
        self.supported = network is not None
        self.wlan = network.WLAN(network.STA_IF) if self.supported else None
        self.next_reconnect_ms = 0
        self.connect_started_ms = 0
        self.connecting = False
        self.last_ssid = None
        self.last_password = None

    def network_state(self):
        if not self.wlan:
            return "off"
        return "on" if self.wlan.isconnected() else "off"

    def is_connected(self):
        return bool(self.wlan and self.wlan.isconnected())

    def current_credentials(self):
        return self.last_ssid, self.last_password

    def disconnect(self):
        self.connecting = False
        self.connect_started_ms = 0
        try:
            if self.wlan:
                self.wlan.disconnect()
        except Exception:
            pass

    def schedule_reconnect(self, delay_ms=None):
        now_ms = time.ticks_ms()
        self.disconnect()
        self.next_reconnect_ms = time.ticks_add(
            now_ms,
            delay_ms if delay_ms is not None else self.reconnect_delay_ms,
        )

    def clear_credentials(self):
        self.last_ssid = None
        self.last_password = None

    def service(self, ssid, password):
        if not self.wlan:
            return False

        ssid = str(ssid or "").strip()
        password = str(password or "").strip()

        if not ssid:
            if self.connecting or self.last_ssid is not None or self.wlan.isconnected():
                print("Wi-Fi disabled: SSID is empty")
            self.disconnect()
            self.clear_credentials()
            return False

        now_ms = time.ticks_ms()
        self.wlan.active(True)

        if self.wlan.isconnected():
            if self.connecting or self.last_ssid is None:
                self.connecting = False
                self.connect_started_ms = 0
                self.last_ssid = ssid
                self.last_password = password
                print("Wi-Fi connected: {}".format(self.wlan.ifconfig()))
                return True

            if self.last_ssid == ssid and self.last_password == password:
                return True

            print("Wi-Fi config changed -> reconnect")
            self.schedule_reconnect(0)
            return False

        if self.connecting:
            if time.ticks_diff(now_ms, self.connect_started_ms) > self.connect_timeout_ms:
                print("Wi-Fi connect timeout: {}".format(ssid))
                self.schedule_reconnect()
            return False

        if time.ticks_diff(now_ms, self.next_reconnect_ms) < 0:
            return False

        try:
            self.wlan.disconnect()
        except Exception:
            pass

        print("Wi-Fi connecting: {}".format(ssid))
        self.wlan.connect(ssid, password)
        self.connecting = True
        self.connect_started_ms = now_ms
        return False
