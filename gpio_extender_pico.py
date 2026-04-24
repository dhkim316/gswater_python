from machine import I2C, Pin
import time

# MCP23008 레지스터 주소
IODIR = 0x00  # 방향 레지스터 (0=output, 1=input)
GPIO = 0x09   # GPIO 레지스터
OLAT = 0x0A  # 출력 래치 레지스터

# MCP23008 I2C 주소 (기본 0x20)
MCP23008_ADDR = 0x20

class GPIOExtender:
    def __init__(self, i2c=None, i2c_id=0, scl_pin=21, sda_pin=20, reset_pin=22, addr=MCP23008_ADDR):
        self.i2c = i2c if i2c is not None else I2C(i2c_id, scl=Pin(scl_pin), sda=Pin(sda_pin))
        self.reset_pin = Pin(reset_pin, Pin.OUT)
        self.addr = addr
        self._relay1_state = None
        self._relay2_state = None
        self._relay3_state = None
        self.reset()
        self.init_mcp23008()

    def reset(self):
        self.reset_pin.value(0)
        time.sleep(0.01)
        self.reset_pin.value(1)
        time.sleep(0.01)

    def init_mcp23008(self):
        # 모든 핀을 출력으로 설정
        self.i2c.writeto_mem(self.addr, IODIR, bytes([0x00]))  # 0x00 = all output
        self.i2c.writeto_mem(self.addr, OLAT, bytes([0x00]))
        self._sync_relay_states()

    def _sync_relay_states(self):
        current = self.i2c.readfrom_mem(self.addr, OLAT, 1)[0]
        self._relay1_state = (current >> 0) & 1
        self._relay2_state = (current >> 1) & 1
        self._relay3_state = (current >> 2) & 1

    def write_pin(self, pin, value):
        if not 0 <= pin <= 7:
            raise ValueError("Pin must be 0-7")
        current = self.i2c.readfrom_mem(self.addr, OLAT, 1)[0]
        if value:
            current |= (1 << pin)
        else:
            current &= ~(1 << pin)
        self.i2c.writeto_mem(self.addr, OLAT, bytes([current]))
        return True

    def read_pin(self, pin):
        if not 0 <= pin <= 7:
            raise ValueError("Pin must be 0-7")
        current = self.i2c.readfrom_mem(self.addr, GPIO, 1)[0]
        return (current >> pin) & 1

    # 릴레이 제어 함수
    def set_relay1_panel_HI_LO(self, state):
        state = 1 if state else 0
        if self._relay1_state == state:
            return False
        written = self.write_pin(0, state)  # ext_gp0
        if written:
            self._relay1_state = state
        return written

    def set_relay2_motor(self, state):
        state = 1 if state else 0
        if self._relay2_state == state:
            return False
        written = self.write_pin(1, state)  # ext_gp1
        if written:
            self._relay2_state = state
        return written

    def set_relay3_alarm(self, state):
        state = 1 if state else 0
        if self._relay3_state == state:
            return False
        written = self.write_pin(2, state)  # ext_gp2
        if written:
            self._relay3_state = state
        return written


if __name__ == '__main__':
    ext = GPIOExtender()
    print('GPIO Extender Agent 시작')
    print('릴레이 제어: 1 (panel), 2 (motor), 3 (alarm), q (종료)')
    try:
        while True:
            cmd = input('명령: ').strip().lower()
            if cmd == 'q':
                break
            elif cmd == '1':
                current = ext.read_pin(0)
                ext.set_relay1_panel_HI_LO(1 - current)  # 토글
                print(f'Relay1: {"ON" if 1 - current else "OFF"}')
            elif cmd == '2':
                current = ext.read_pin(1)
                ext.set_relay2_motor(1 - current)
                print(f'Relay2: {"ON" if 1 - current else "OFF"}')
            elif cmd == '3':
                current = ext.read_pin(2)
                ext.set_relay3_alarm(1 - current)
                print(f'Relay3: {"ON" if 1 - current else "OFF"}')
            else:
                print('잘못된 명령')
    except KeyboardInterrupt:
        print('종료')
