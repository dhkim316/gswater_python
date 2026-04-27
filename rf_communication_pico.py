from machine import UART, Pin
import time

class RFCommunicator:
    def __init__(self, uart_id=0, tx_pin=16, rx_pin=17, baudrate=9600, reset_pin=19, ch_pins=None):
        if ch_pins is None:
            ch_pins = (13, 14, 15, 18)
        self.uart = UART(uart_id, baudrate=baudrate, tx=tx_pin, rx=rx_pin)
        self.reset_pin = Pin(reset_pin, 1)  # Pin.OUT = 1
        self.ch_pins = [Pin(pin, 1) for pin in ch_pins]  # Pin.OUT = 1
        self.reset()  # 초기 리셋

    def reset(self):
        self.reset_pin.value(0)
        time.sleep(0.1)
        self.reset_pin.value(1)

    def select_channel(self, channel):
        """채널 선택 (0-15)"""
        if not 0 <= channel <= 15:
            raise ValueError("Channel must be between 0 and 15")
        for i in range(4):
            bit = (channel >> i) & 1
            self.ch_pins[i].value(bit)

    def send(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        self.uart.write(data)

    def receive(self, size=0):
        if size > 0:
            return self.uart.read(size)
        else:
            return self.uart.read()

    def any(self):
        try:
            return self.uart.any()
        except AttributeError:
            return 0

    def receive_available(self):
        count = self.any()
        if count:
            return self.receive(count)
        return None

    def close(self):
        self.uart.deinit()

# 사용 예시
if __name__ == "__main__":
    rf = RFCommunicator()
    rf.select_channel(9)  # 예시: 채널 9 선택
    time.sleep(0.1)  # 간단한 타임아웃

    while True:
        # 데이터 송신
        rf.send("{SA}")
        # 데이터 수신 (타임아웃까지)
        time.sleep(1)  # 간단한 타임아웃
        data = rf.receive()
        if data:
            try:
                text = data.decode('utf-8')
            except Exception:
                # MicroPython에서는 errors 파라미터 미지원
                text = ''.join(chr(b) for b in data if 32 <= b < 127)
            print("Received:", text)

    rf.close()
        
