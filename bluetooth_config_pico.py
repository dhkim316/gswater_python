import json

DEFAULT_ATT_MTU = 23
ATT_NOTIFY_OVERHEAD = 3
DEFAULT_NOTIFY_CHUNK = DEFAULT_ATT_MTU - ATT_NOTIFY_OVERHEAD
PREFERRED_MTU = 247
RX_BUFFER_SIZE = 1024
QUEUE_COMPACT_THRESHOLD = 16


class BluetoothConfigServer:
    def __init__(self, device_name="GSWater"):
        self.device_name = device_name
        self.enabled = False
        self._rx_lines = []
        self._rx_line_index = 0
        self._rx_partial = b""
        self._events = []
        self._event_index = 0
        self._ble = None
        self._connections = set()
        self._conn_mtu = {}
        self._handle_tx = None
        self._handle_rx = None

        try:
            import bluetooth
            from micropython import const
        except ImportError:
            print("Bluetooth disabled: module not available")
            return

        self._bluetooth = bluetooth
        self._const = const
        self._setup_ble()

    def _setup_ble(self):
        bluetooth = self._bluetooth
        const = self._const

        irq_central_connect = const(1)
        irq_central_disconnect = const(2)
        irq_gatts_write = const(3)
        irq_mtu_exchanged = const(21)
        flag_write = const(0x0008)
        flag_notify = const(0x0010)

        uart_service_uuid = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
        uart_rx_uuid = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
        uart_tx_uuid = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

        uart_service = (
            uart_service_uuid,
            (
                (uart_tx_uuid, flag_notify),
                (uart_rx_uuid, flag_write),
            ),
        )

        ble = bluetooth.BLE()
        ble.active(True)
        try:
            ble.config(mtu=PREFERRED_MTU)
        except Exception:
            pass
        ble.irq(self._irq)
        handles = ble.gatts_register_services((uart_service,))
        self._handle_tx, self._handle_rx = handles[0]
        ble.gatts_set_buffer(self._handle_rx, RX_BUFFER_SIZE, True)

        self._IRQ_CENTRAL_CONNECT = irq_central_connect
        self._IRQ_CENTRAL_DISCONNECT = irq_central_disconnect
        self._IRQ_GATTS_WRITE = irq_gatts_write
        self._IRQ_MTU_EXCHANGED = irq_mtu_exchanged
        self._ble = ble
        self.enabled = True
        self._advertise()
        print("Bluetooth BLE UART ready as '{}'".format(self.device_name))

    def _irq(self, event, data):
        if event == self._IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            self._conn_mtu[conn_handle] = self._get_local_mtu()
            self._events.append("connected")
            self.send_status({"event": "connected"})
            return

        if event == self._IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            if conn_handle in self._connections:
                self._connections.remove(conn_handle)
            if conn_handle in self._conn_mtu:
                del self._conn_mtu[conn_handle]
            self._events.append("disconnected")
            self._advertise()
            return

        if event == self._IRQ_MTU_EXCHANGED:
            conn_handle, mtu = data
            self._conn_mtu[conn_handle] = mtu
            print("BT MTU conn={} mtu={}".format(conn_handle, mtu))
            return

        if event != self._IRQ_GATTS_WRITE:
            return

        conn_handle, value_handle = data
        if value_handle != self._handle_rx:
            return

        raw = self._ble.gatts_read(self._handle_rx)
        if not raw:
            return

        self._buffer_rx(raw)

    def _buffer_rx(self, raw):
        data = self._rx_partial + bytes(raw).replace(b"\r", b"\n")
        chunks = data.split(b"\n")
        self._rx_partial = chunks.pop()

        for chunk in chunks:
            line_bytes = chunk.strip()
            if not line_bytes:
                continue
            try:
                line = line_bytes.decode("utf-8")
            except UnicodeError:
                self.send_error("utf8")
                continue
            self._rx_lines.append(line)

    def _pop_buffered(self, items, index_attr):
        index = getattr(self, index_attr)
        if index >= len(items):
            return None

        value = items[index]
        index += 1

        if index >= len(items):
            del items[:]
            index = 0
        elif index >= QUEUE_COMPACT_THRESHOLD and index * 2 >= len(items):
            del items[:index]
            index = 0

        setattr(self, index_attr, index)
        return value

    def _advertise(self):
        if not self.enabled:
            return

        name = self.device_name.encode("utf-8")
        payload = bytearray((2, 0x01, 0x06, len(name) + 1, 0x09))
        payload.extend(name)
        self._ble.gap_advertise(100000, adv_data=payload)

    def has_pending(self):
        return self._rx_line_index < len(self._rx_lines)

    def has_event(self):
        return self._event_index < len(self._events)

    def is_connected(self):
        return bool(self._connections)

    def read_event(self):
        return self._pop_buffered(self._events, "_event_index")

    def read_command(self):
        return self._pop_buffered(self._rx_lines, "_rx_line_index")

    def send_text(self, text):
        if not self.enabled:
            return

        payload = str(text)
        if not payload.endswith("\n"):
            payload += "\n"

        print("BT TX -> {}".format(payload.strip()))
        if not self._connections:
            return

        data = payload.encode("utf-8")
        for conn_handle in self._connections:
            offset = 0
            total = len(data)
            while offset < total:
                chunk_size = self._notify_chunk_size(conn_handle)
                chunk = data[offset:offset + chunk_size]
                try:
                    self._ble.gatts_notify(conn_handle, self._handle_tx, chunk)
                except Exception:
                    break
                offset += len(chunk)

    def send_status(self, payload):
        self.send_text(json.dumps(payload))

    def send_error(self, reason, key=None, value=None):
        payload = {"status": "error", "reason": reason}
        if key is not None:
            payload["key"] = key
        if value is not None:
            payload["value"] = value
        self.send_status(payload)

    def _get_local_mtu(self):
        try:
            mtu = self._ble.config("mtu")
            if mtu:
                return mtu
        except Exception:
            pass
        return DEFAULT_ATT_MTU

    def _notify_chunk_size(self, conn_handle):
        mtu = self._conn_mtu.get(conn_handle, self._get_local_mtu())
        size = mtu - ATT_NOTIFY_OVERHEAD
        if size < 1:
            return DEFAULT_NOTIFY_CHUNK
        return size
