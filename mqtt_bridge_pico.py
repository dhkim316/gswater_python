import time

try:
    import machine
except ImportError:
    machine = None

try:
    import ubinascii
except ImportError:
    ubinascii = None

try:
    import ujson as json
except ImportError:
    import json

try:
    from umqtt.simple import MQTTClient
except ImportError:
    MQTTClient = None

from wifi_manager_pico import WifiStationManager


DISPLAY_REGION_DEFAULT = "\uBBF8\uC124\uC815"
FAST_RUNTIME_KEYS = (
    "water_level_pct",
    "well_depth_m",
    "current_a",
    "flow_ton",
    "solar",
    "battery_pct",
    "rf_ant",
)
MQTT_ERR_CONNRESET = 104
MQTT_ERR_TIMEDOUT = 110
MQTT_ERR_SOCK_CLOSED = -1


class MqttBridge:
    def __init__(
        self,
        mqtt_user_id="1",
        mqtt_port=1883,
        keepalive_sec=60,
        mqtt_connect_timeout_sec=5,
        mqtt_io_timeout_sec=60,
        mqtt_operation_timeout_sec=0.2,
        publish_interval_ms=5000,
        meta_publish_interval_ms=3600000,
        ping_interval_ms=30000,
        ping_response_timeout_ms=15000,
        reconnect_delay_ms=5000,
        max_publish_failures=4,
        max_service_failures=4,
        max_connect_failures_before_wifi_reconnect=4,
        wifi_connect_timeout_ms=20000,
        wifi_poll_sleep_ms=300,
        default_display_region=DISPLAY_REGION_DEFAULT,
    ):
        self.mqtt_user_id = str(mqtt_user_id)
        self.mqtt_port = mqtt_port
        self.keepalive_sec = keepalive_sec
        self.mqtt_connect_timeout_sec = mqtt_connect_timeout_sec
        self.mqtt_io_timeout_sec = mqtt_io_timeout_sec
        self.mqtt_operation_timeout_sec = mqtt_operation_timeout_sec
        self.publish_interval_ms = publish_interval_ms
        self.meta_publish_interval_ms = meta_publish_interval_ms
        self.ping_interval_ms = ping_interval_ms
        self.ping_response_timeout_ms = ping_response_timeout_ms
        self.reconnect_delay_ms = reconnect_delay_ms
        self.max_publish_failures = max(1, int(max_publish_failures))
        self.max_service_failures = max(1, int(max_service_failures))
        self.max_connect_failures_before_wifi_reconnect = max(
            1,
            int(max_connect_failures_before_wifi_reconnect),
        )
        self.wifi_connect_timeout_ms = wifi_connect_timeout_ms
        self.default_display_region = default_display_region
        self.supported = MQTTClient is not None
        self.wifi = WifiStationManager(
            reconnect_delay_ms=reconnect_delay_ms,
            connect_timeout_ms=wifi_connect_timeout_ms,
        )
        self.client = None
        self.next_mqtt_reconnect_ms = 0
        self.last_publish_ms = 0
        self.last_meta_publish_ms = 0
        self.last_ping_ms = 0
        self.ping_sent_ms = 0
        self.awaiting_pingresp = False
        self.last_broker = ""
        self.last_meta_signature = ""
        self.identity_cache = {
            "region_code": "KR00",
            "display_region": default_display_region,
            "device_code": "0000",
        }
        self.pump_control_mode = "auto"
        self.pump_override = None
        self.pending_pump_command = None
        self.pending_pump_result = None
        self.pending_force_publish = False
        self.mqtt_publish_failures = 0
        self.mqtt_connect_failures = 0
        self.mqtt_service_failures = 0

    def _text(self, value):
        return str(value if value is not None else "").strip()

    def _config_value(self, config, key):
        parts = config.get(key, []) if isinstance(config, dict) else []
        return parts[0] if parts else ""

    def _pad_left(self, value, width, fill="0"):
        raw = self._text(value)
        if len(raw) >= width:
            return raw
        return (fill * (width - len(raw))) + raw

    def _normalized_broker_host(self, config):
        raw = self._text(self._config_value(config, "SET_SERVER_IP_TXT"))
        parts = [part for part in raw.split(".") if part != ""]
        if len(parts) == 4 and all(part.isdigit() for part in parts):
            values = [str(int(part)) for part in parts]
            return ".".join(values)
        return raw

    def _normalized_region_code(self, raw_region):
        raw = self._text(raw_region)
        if not raw:
            return "KR00"
        return raw.replace("/", "-")

    def _display_region(self, raw_region, region_code):
        raw = self._text(raw_region)
        if raw:
            return raw
        return region_code or self.default_display_region

    def _normalized_device_code(self, raw_device):
        raw = self._text(raw_device).upper()
        digits = "".join(ch for ch in raw if "0" <= ch <= "9")
        if digits and digits == raw:
            return self._pad_left(digits[-4:], 4, "0")

        filtered = "".join(ch for ch in raw if ("0" <= ch <= "9") or ("A" <= ch <= "Z"))
        if not filtered:
            return "0000"
        if len(filtered) >= 4:
            return filtered[-4:]
        return self._pad_left(filtered, 4, "0")

    def identity(self, config):
        raw_region = self._config_value(config, "SET_REGION_TXT")
        raw_device = self._config_value(config, "SET_SERIAL_NUM_TXT")
        region_code = self._normalized_region_code(raw_region)
        identity = {
            "region_code": region_code,
            "display_region": self._display_region(raw_region, region_code),
            "device_code": self._normalized_device_code(raw_device),
        }
        self.identity_cache = identity
        return identity

    def is_connected(self):
        return self.client is not None

    def network_state(self):
        return self.wifi.network_state()

    def get_pump_override(self):
        return self.pump_override

    def get_pump_control_mode(self):
        return self.pump_control_mode

    def pop_pending_pump_result(self):
        result = self.pending_pump_result
        self.pending_pump_result = None
        return result

    def pop_pending_pump_command(self):
        command = self.pending_pump_command
        self.pending_pump_command = None
        return command

    def request_publish(self):
        self.pending_force_publish = True

    def should_publish(self, now_ms):
        if not self.client:
            return False
        if self.pending_force_publish:
            return True
        return time.ticks_diff(now_ms, self.last_publish_ms) >= self.publish_interval_ms

    def _stable_signature(self, payload):
        if not isinstance(payload, dict):
            return self._text(payload)
        items = []
        for key in sorted(payload.keys()):
            items.append([self._text(key), payload[key]])
        return json.dumps(items)

    def _split_runtime_data(self, data):
        fast_data = {}
        slow_data = {}
        for key, value in (data or {}).items():
            if key in FAST_RUNTIME_KEYS:
                fast_data[key] = value
            else:
                slow_data[key] = value
        return fast_data, slow_data

    def _should_publish_meta(self, meta_data):
        signature = self._stable_signature(meta_data)
        if not self.last_meta_signature:
            return True, signature
        if signature != self.last_meta_signature:
            return True, signature
        if time.ticks_diff(time.ticks_ms(), self.last_meta_publish_ms) >= self.meta_publish_interval_ms:
            return True, signature
        return False, signature

    def _make_client_id(self):
        prefix = "gswater-"
        identity = self.identity_cache
        suffix = "{}".format(identity["region_code"])
        if machine is not None and ubinascii is not None:
            unique = ubinascii.hexlify(machine.unique_id()).decode("ascii")
        else:
            unique = str(time.ticks_ms())
        return (prefix + suffix + "-" + unique).encode("utf-8")

    def _publish_json(self, topic, payload, retain=False):
        if not self.client:
            return False

        try:
            body = json.dumps(payload)
            if isinstance(body, str):
                body = body.encode("utf-8")
            if isinstance(topic, str):
                topic = topic.encode("utf-8")
            self.client.set_timeout(self._operation_timeout(self.mqtt_io_timeout_sec))
            self.client.publish(topic, body, retain=retain)
            self.mqtt_publish_failures = 0
            return True
        except Exception as exc:
            self.mqtt_publish_failures += 1
            print(
                "MQTT publish failed: count={}/{} error={}".format(
                    self.mqtt_publish_failures,
                    self.max_publish_failures,
                    exc,
                )
            )
            if (not self.wifi.is_connected()) or self.mqtt_publish_failures >= self.max_publish_failures:
                self._schedule_mqtt_reconnect(self._mqtt_reconnect_delay_ms(exc))
            return False

    def _mqtt_errno(self, exc):
        if not isinstance(exc, OSError):
            return None
        args = getattr(exc, "args", None)
        if not args:
            return None
        return args[0]

    def _is_mqtt_connection_error(self, exc):
        err = self._mqtt_errno(exc)
        return err in (MQTT_ERR_CONNRESET, MQTT_ERR_TIMEDOUT, MQTT_ERR_SOCK_CLOSED)

    def _mqtt_reconnect_delay_ms(self, exc):
        if self._is_mqtt_connection_error(exc):
            return 0
        return self.reconnect_delay_ms

    def _operation_timeout(self, configured_timeout):
        if configured_timeout is None:
            return self.mqtt_operation_timeout_sec
        if self.mqtt_operation_timeout_sec is None:
            return configured_timeout
        try:
            configured = float(configured_timeout)
            operation = float(self.mqtt_operation_timeout_sec)
        except (TypeError, ValueError):
            return configured_timeout
        if configured <= 0:
            return configured_timeout
        if operation <= 0:
            return configured_timeout
        return min(configured, operation)

    def _legacy_payload(self, identity, topic_name, timestamp, value):
        return {
            "region": identity["display_region"],
            "type": topic_name,
            "timestamp": timestamp,
            "value": value,
        }

    def publish_runtime(self, config, snapshot):
        if not self.client:
            print("MQTT publish skipped: disconnected")
            return False

        identity = self.identity(config)
        data = dict(snapshot.get("data") or {})
        timestamp = self._text(snapshot.get("timestamp"))
        publish_dashboard = bool(snapshot.get("publish_dashboard", True))
        topic_prefix = "{}/pico/{}/".format(self.mqtt_user_id, identity["region_code"])
        fast_data, slow_data = self._split_runtime_data(data)
        meta_due, meta_signature = self._should_publish_meta(slow_data)

        success = True

        if publish_dashboard:
            dashboard_payload = {
                "timestamp": timestamp,
                "data": fast_data,
            }
            print("MQTT publish dashboard_state raw={}".format(json.dumps(dashboard_payload)))
            success = self._publish_json(topic_prefix + "dashboard_state", dashboard_payload) and success
            print(
                "MQTT publish dashboard_state: topic={} ok={}".format(
                    topic_prefix + "dashboard_state",
                    success,
                )
            )

        if meta_due:
            meta_payload = {
                "timestamp": timestamp,
                "data": slow_data,
            }
            print("MQTT publish dashboard_meta raw={}".format(json.dumps(meta_payload)))
            meta_ok = self._publish_json(topic_prefix + "dashboard_meta", meta_payload, retain=True)
            success = meta_ok and success
            print(
                "MQTT publish dashboard_meta: topic={} ok={}".format(
                    topic_prefix + "dashboard_meta",
                    meta_ok,
                )
            )
            if meta_ok:
                self.last_meta_publish_ms = time.ticks_ms()
                self.last_meta_signature = meta_signature

        if publish_dashboard:
            self.last_publish_ms = time.ticks_ms()
            self.pending_force_publish = False
        return success

    def publish_pump_state(self, config, pump_state, result, timestamp, command=None):
        if not self.client:
            return False

        identity = self.identity(config)
        payload = {
            "timestamp": timestamp,
            "mode": self.pump_control_mode,
            "pump": "on" if str(pump_state).lower() == "on" else "off",
            "result": self._text(result) or "applied",
        }
        if command is not None:
            payload["command"] = self._text(command)
        topic = "{}/pico/{}/pump_state".format(self.mqtt_user_id, identity["region_code"])
        return self._publish_json(topic, payload)

    def _parse_pump_command(self, raw_text):
        text = self._text(raw_text)
        if not text or text == "[object Object]":
            return None

        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None

        if isinstance(parsed, dict):
            command = parsed.get("command", parsed.get("value", parsed.get("state", parsed.get("pump"))))
            normalized = self._normalize_pump_command(command)
            if normalized is not None:
                return normalized

        return self._normalize_pump_command(text)

    def _normalize_pump_command(self, value):
        if value is None:
            return None
        if isinstance(value, bool):
            return "on" if value else "off"
        if isinstance(value, (int, float)):
            return "on" if int(value) == 1 else "off"

        text = self._text(value).lower()
        if text in ("on", "1", "true"):
            return "on"
        if text in ("off", "0", "false"):
            return "off"
        if text in ("manual", "man"):
            return "manual"
        if text in ("auto", "clear", "none"):
            return "auto"
        return None

    def _matches_target(self, parts):
        if len(parts) < 4 or parts[0] != self.mqtt_user_id or parts[1] != "pico":
            return False

        identity = self.identity_cache
        target_device = parts[3] if len(parts) >= 5 else ""
        if parts[2] != identity["region_code"]:
            return False
        if len(parts) >= 5 and target_device and target_device != identity["device_code"]:
            return False
        return True

    def _on_message(self, topic, msg):
        try:
            topic_text = topic.decode("utf-8")
            msg_text = msg.decode("utf-8")
        except Exception as exc:
            print("MQTT decode failed: {}".format(exc))
            return

        parts = topic_text.split("/")
        if not self._matches_target(parts):
            return
        topic_name = parts[-1]
        if topic_name == "pump_cmd":
            command = self._parse_pump_command(msg_text)
            self.pending_pump_command = command if command is not None else "invalid"
            if command == "manual":
                self.pump_control_mode = "manual"
                self.pump_override = None
                self.pending_pump_result = "mode-applied"
            elif command == "auto":
                self.pump_control_mode = "auto"
                self.pump_override = None
                self.pending_pump_result = "mode-applied"
            elif command in ("on", "off"):
                if self.pump_control_mode == "manual":
                    self.pump_override = command
                    self.pending_pump_result = "applied"
                else:
                    self.pending_pump_result = "rejected"
            else:
                self.pending_pump_result = "rejected"

            self.pending_force_publish = True
            print("MQTT pump_cmd -> {}".format(command if command is not None else "invalid"))
            return

    def _schedule_wifi_reconnect(self, delay_ms=None):
        now_ms = time.ticks_ms()
        self._disconnect_mqtt()
        self.next_mqtt_reconnect_ms = time.ticks_add(now_ms, delay_ms if delay_ms is not None else self.reconnect_delay_ms)
        self.wifi.schedule_reconnect(delay_ms)

    def _schedule_mqtt_reconnect(self, delay_ms=None):
        now_ms = time.ticks_ms()
        self._disconnect_mqtt()
        self.next_mqtt_reconnect_ms = time.ticks_add(now_ms, delay_ms if delay_ms is not None else self.reconnect_delay_ms)

    def _disconnect_mqtt(self):
        if self.client is not None:
            try:
                self.client.disconnect()
            except Exception:
                pass
        self.client = None
        self.ping_sent_ms = 0
        self.awaiting_pingresp = False

    def _disconnect(self):
        self._disconnect_mqtt()
        self.wifi.disconnect()

    def _wifi_credentials(self, config):
        ssid = self._text(self._config_value(config, "SET_SSID_TXT"))
        password = self._text(self._config_value(config, "SET_PASS_TXT"))
        return ssid, password

    def _service_wifi(self, config):
        if not self.wifi.supported:
            return False

        ssid, password = self._wifi_credentials(config)
        was_connected = self.wifi.is_connected()
        connected = self.wifi.service(ssid, password)
        if connected and not was_connected:
            self.next_mqtt_reconnect_ms = time.ticks_ms()
        return connected

    def _connect_mqtt(self, config):
        broker = self._normalized_broker_host(config)
        if not broker:
            raise RuntimeError("MQTT broker is empty")

        self.identity(config)

        client = MQTTClient(
            self._make_client_id(),
            broker,
            port=self.mqtt_port,
            keepalive=self.keepalive_sec,
        )
        client.set_callback(self._on_message)
        client.connect(timeout=self._operation_timeout(self.mqtt_connect_timeout_sec))
        client.set_timeout(self._operation_timeout(self.mqtt_connect_timeout_sec))
        self.client = client
        client.subscribe("{}/pico/#".format(self.mqtt_user_id).encode("utf-8"))
        client.set_timeout(self._operation_timeout(self.mqtt_io_timeout_sec))

        self.last_broker = broker
        self.last_ping_ms = time.ticks_ms()
        self.ping_sent_ms = 0
        self.awaiting_pingresp = False
        self.last_meta_publish_ms = 0
        self.last_meta_signature = ""
        self.mqtt_publish_failures = 0
        self.mqtt_connect_failures = 0
        self.mqtt_service_failures = 0
        self.pending_force_publish = True
        print(
            "MQTT connected: broker={} region={}".format(
                broker,
                self.identity_cache["region_code"],
            )
        )

    def _service_mqtt_receive(self):
        operation = self.client.check_msg()
        if operation == 0xD0:
            self.awaiting_pingresp = False
            self.ping_sent_ms = 0
        if operation is not None:
            self.mqtt_service_failures = 0
        return operation

    def _service_mqtt_ping(self, now_ms):
        if self.awaiting_pingresp:
            if time.ticks_diff(now_ms, self.ping_sent_ms) >= self.ping_response_timeout_ms:
                raise OSError(MQTT_ERR_TIMEDOUT)
            return
        if time.ticks_diff(now_ms, self.last_ping_ms) < self.ping_interval_ms:
            return
        self.client.set_timeout(self._operation_timeout(self.mqtt_io_timeout_sec))
        self.client.ping()
        self.last_ping_ms = now_ms
        self.ping_sent_ms = now_ms
        self.awaiting_pingresp = True

    def _handle_mqtt_service_error(self, label, exc):
        self.mqtt_service_failures += 1
        err = self._mqtt_errno(exc)
        if self._is_mqtt_connection_error(exc):
            print(
                "MQTT {} disconnected: count={}/{} errno={} error={}".format(
                    label,
                    self.mqtt_service_failures,
                    self.max_service_failures,
                    err,
                    exc,
                )
            )
        else:
            print(
                "MQTT {} failed: count={}/{} error={}".format(
                    label,
                    self.mqtt_service_failures,
                    self.max_service_failures,
                    exc,
                )
            )
        if self.mqtt_service_failures >= self.max_service_failures:
            self.mqtt_service_failures = 0
            self._schedule_mqtt_reconnect(self._mqtt_reconnect_delay_ms(exc))

    def service(self, config):
        if not self.supported:
            return False

        identity = self.identity(config)
        broker = self._normalized_broker_host(config)
        wifi_connected = self._service_wifi(config)

        if not wifi_connected:
            if self.client is not None:
                print("Wi-Fi disconnected -> MQTT reconnect pending")
                self._schedule_mqtt_reconnect(0)
            return False

        if self.client is not None and broker and broker != self.last_broker:
            print("MQTT broker changed -> reconnect")
            self._schedule_mqtt_reconnect(0)

        if self.client is None:
            now_ms = time.ticks_ms()
            if time.ticks_diff(now_ms, self.next_mqtt_reconnect_ms) < 0:
                return False
            try:
                self._connect_mqtt(config)
                return True
            except Exception as exc:
                self.mqtt_connect_failures += 1
                print(
                    "MQTT connect failed: count={}/{} broker={} region={} error={}".format(
                        self.mqtt_connect_failures,
                        self.max_connect_failures_before_wifi_reconnect,
                        broker,
                        identity["region_code"],
                        exc,
                    )
                )
                if self.mqtt_connect_failures >= self.max_connect_failures_before_wifi_reconnect:
                    print("MQTT connect failed repeatedly -> Wi-Fi reconnect")
                    self.mqtt_connect_failures = 0
                    self._schedule_wifi_reconnect()
                else:
                    self._schedule_mqtt_reconnect()
                return False

        try:
            self._service_mqtt_receive()
        except Exception as exc:
            self._handle_mqtt_service_error("receive", exc)
            return False

        try:
            self._service_mqtt_ping(time.ticks_ms())
        except Exception as exc:
            self._handle_mqtt_service_error("ping", exc)
            return False

        return True
