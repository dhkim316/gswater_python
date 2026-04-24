from machine import Pin
import time

# HC165 연결 핀, gswater.txt 기준
PL_PIN = 6
CLK_PIN = 7
DATA_PIN = 8

btn_map = {
    7: 'btn_up',
    6: 'btn_down',
    5: 'btn_left',
    4: 'btn_right',
    3: 'btn_set',
    2: 'btn_enter',
    1: 'btn_esc',
    0: 'btn_reset',
}

pl = Pin(PL_PIN, Pin.OUT)
clk = Pin(CLK_PIN, Pin.OUT)
data = Pin(DATA_PIN, Pin.IN, Pin.PULL_UP)


def read_hc165():
    # Load parallel inputs to shift register
    pl.value(0)
    time.sleep_us(2)
    pl.value(1)
    time.sleep_us(2)

    value = 0
    for bit in range(8):
        clk.value(0)
        time.sleep_us(2)
        bit_val = data.value()
        # HC165 active low 버튼 입력 (문서 따라 다름) : 0=pressed
        if bit_val == 0:
            value |= (1 << bit)
        clk.value(1)
        time.sleep_us(2)

    return value


def decode_buttons(raw):
    pressed = []
    for bit, name in btn_map.items():
        if raw & (1 << bit):
            pressed.append(name)
    return pressed


if __name__ == '__main__':
    print('Button Input Agent 시작')
    try:
        while True:
            read = read_hc165()
            pressed = decode_buttons(read)
            if pressed:
                print('Pressed:', ', '.join(pressed))
            time.sleep(0.1)
    except KeyboardInterrupt:
        print('종료')
