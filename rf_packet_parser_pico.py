"""
MicroPython helper for receiving and parsing GSWater RF packets.

This module extracts the receive/parsing logic from waterMain.py
without changing the original desktop code.

TX format from sender firmware:
    U<target_addr>UQ<version><value3><battery><solar><checksum>
    U<target_addr>UP<version><value3><battery><solar><checksum>

Example frame before checksum:
    U01UQR24231
    U01UPR34620

Meaning:
    [0:4] frame prefix: U + target address 2 digits + U
    [4]   sensor type: Q=oddugi, P=pressure
    [5]   hardware/version code
    [6:9] sensor value, 3 ASCII digits
    [9]   battery level: '1' / '2' / '3'
    [10]  solar flag: '0' / '1'
    [11]  checksum = sum(frame[4:11]) & 0xFF
"""


def safe_ascii_decode(data):
    try:
        return data.decode("ascii")
    except Exception:
        chars = []
        for value in data:
            if 32 <= value < 127:
                chars.append(chr(value))
            else:
                chars.append("?")
        return "".join(chars)


def calc_checksum(data):
    return sum(data) & 0xFF


def verify_frame(frame):
    """
    Validate a GSWater frame with checksum.

    Format:
    - 4 bytes prefix: U + 2-digit address + U
    - 7 bytes ASCII payload: Q|P + version + 3 digits + battery + solar
    - 1 byte checksum = sum(frame[4:11]) & 0xFF
    """
    if not frame or len(frame) != 12:
        return False

    if frame[0:1] != b"U" or frame[3:4] != b"U":
        return False

    if not (48 <= frame[1] <= 57 and 48 <= frame[2] <= 57):
        return False

    if frame[4:5] not in (b"Q", b"P"):
        return False

    data = frame[4:11]
    expected_checksum = frame[11]
    return calc_checksum(data) == expected_checksum


def extract_valid_frame(raw_packet):
    """
    Extract the last valid 12-byte frame from a UART read buffer.
    """
    if not raw_packet or len(raw_packet) < 12:
        return None

    start = len(raw_packet) - 12
    while start >= 0:
        frame = raw_packet[start:start + 12]
        if verify_frame(frame):
            return frame
        start -= 1

    return None


def parse_frame(frame):
    """
    Parse a validated 12-byte GSWater frame.

    Payload layout from sender firmware:
    - [0:4] frame prefix: UxxU
    - [4]   sensor type: 'Q' or 'P'
    - [5]   version
    - [6:9] sensor value
    - [9]   battery
    - [10]  solar
    """
    if not verify_frame(frame):
        return None

    address = safe_ascii_decode(frame[1:3])
    text = safe_ascii_decode(frame[4:11])
    sensor_type = text[0:1]
    version = text[1:2]
    sensor_value = text[2:5]
    battery = text[5:6]
    solar = text[6:7]

    return {
        "raw_frame": frame,
        "raw_text": text,
        "address": address,
        "sensor_type": sensor_type,
        "version": version,
        "tank_version": text[0:2],
        "pole3": "00",
        "sensor_value": sensor_value,
        "oddugi": sensor_value,
        "pressure": sensor_value,
        "battery": battery,
        "solar": solar,
        "checksum": frame[11],
    }


def receive_and_parse(rf):
    """
    Read from RFCommunicator and return parsed packet info.

    Returns:
    - dict: parsed packet data
    - None: when no valid packet is available
    """
    raw_packet = rf.receive()
    frame = extract_valid_frame(raw_packet)
    if not frame:
        return None
    return parse_frame(frame)


if __name__ == "__main__":
    import time
    from rf_communication_pico import RFCommunicator

    rf = RFCommunicator()
    rf.select_channel(9)

    try:
        while True:
            rf.send("{SA}")
            time.sleep_ms(500)

            parsed = receive_and_parse(rf)
            if parsed:
                print("RX:", parsed["raw_text"])
                print("tank_version:", parsed["tank_version"])
                print("sensor:", parsed["pressure"])
                print("battery:", parsed["battery"])
                print("solar:", parsed["solar"])

            time.sleep_ms(500)
    finally:
        rf.close()
