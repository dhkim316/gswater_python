from machine import I2C, Pin


ISL1208_ADDRESS = 0x6F

ISL1208_SC = 0x00
ISL1208_MN = 0x01
ISL1208_HR = 0x02
ISL1208_DT = 0x03
ISL1208_MO = 0x04
ISL1208_YR = 0x05
ISL1208_DW = 0x06

ISL1208_SR = 0x07
ISL1208_INT = 0x08
ISL1208_ATR = 0x0A
ISL1208_DTR = 0x0B

ISL1208_SCA = 0x0C
ISL1208_MNA = 0x0D
ISL1208_HRA = 0x0E
ISL1208_DTA = 0x0F
ISL1208_MOA = 0x10
ISL1208_DWA = 0x11

ISL1208_USR1 = 0x12
ISL1208_USR2 = 0x13

SR_WRTC = 0x10
ALARM_ENABLE_MASK = 0x80
HR_MIL_MASK = 0x80
HR_PM_MASK = 0x20
HR_24H_MASK = 0x3F
HR_12H_MASK = 0x1F


class ISL1208RTC:
    DAY_NAMES = (
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    )

    def __init__(self, i2c=None, i2c_id=0, scl_pin=21, sda_pin=20, addr=ISL1208_ADDRESS):
        self.i2c = i2c if i2c is not None else I2C(i2c_id, scl=Pin(scl_pin), sda=Pin(sda_pin))
        self.addr = addr
        self.startOfTheWeek = 0
        self._reset_cached_values()

        devices = self.i2c.scan()
        self._active = self.addr in devices
        if not self._active:
            raise OSError(
                "ISL1208 not found at 0x{:02X}, found: {}".format(
                    self.addr, [hex(device) for device in devices]
                )
            )

        self.begin()

    def _reset_cached_values(self):
        self.yearValue = 0
        self.monthValue = 0
        self.dateValue = 0
        self.dayValue = 0
        self.hourValue = 0
        self.minuteValue = 0
        self.secondValue = 0
        self.periodValue = 0

        self.monthValueAlarm = 0
        self.dateValueAlarm = 0
        self.dayValueAlarm = 0
        self.hourValueAlarm = 0
        self.minuteValueAlarm = 0
        self.secondValueAlarm = 0
        self.periodValueAlarm = 0

    def begin(self):
        self._reset_cached_values()
        self.write_register(ISL1208_SR, SR_WRTC)
        self.write_register(ISL1208_ATR, 7)
        self.set_fout_32768()

    def isRtcActive(self):
        return self._active

    def probe(self):
        try:
            self.i2c.readfrom_mem(self.addr, ISL1208_SR, 1)
            self._active = True
            return True
        except Exception:
            self._active = False
            return False

    def read_register(self, reg):
        try:
            value = self.i2c.readfrom_mem(self.addr, reg, 1)[0]
            self._active = True
            return value
        except Exception:
            self._active = False
            raise

    def write_register(self, reg, value):
        try:
            self.i2c.writeto_mem(self.addr, reg, bytes((value & 0xFF,)))
            self._active = True
        except Exception:
            self._active = False
            raise

    def read_registers(self, reg, length):
        try:
            values = self.i2c.readfrom_mem(self.addr, reg, length)
            self._active = True
            return values
        except Exception:
            self._active = False
            raise

    def write_registers(self, reg, values):
        try:
            self.i2c.writeto_mem(self.addr, reg, bytes(values))
            self._active = True
        except Exception:
            self._active = False
            raise

    def bcdToDec(self, value):
        return ((value >> 4) * 10) + (value & 0x0F)

    def decToBcd(self, value):
        return ((value // 10) << 4) | (value % 10)

    def _validate_time_fields(self):
        return not (
            self.yearValue > 99
            or self.monthValue < 1
            or self.monthValue > 12
            or self.dateValue < 1
            or self.dateValue > 31
            or self.hourValue > 23
            or self.minuteValue > 59
            or self.secondValue > 59
            or self.dayValue > 6
            or self.periodValue not in (0, 1)
        )

    def _validate_alarm_fields(self):
        return not (
            self.monthValueAlarm < 1
            or self.monthValueAlarm > 12
            or self.dateValueAlarm < 1
            or self.dateValueAlarm > 31
            or self.hourValueAlarm > 23
            or self.minuteValueAlarm > 59
            or self.secondValueAlarm > 59
            or self.dayValueAlarm > 6
            or self.periodValueAlarm not in (0, 1)
        )

    def _encode_hour(self, hour_value, period_value):
        del period_value
        return HR_MIL_MASK | (self.decToBcd(hour_value) & HR_24H_MASK)

    def _decode_hour(self, raw_value):
        if raw_value & HR_MIL_MASK:
            hour = self.bcdToDec(raw_value & HR_24H_MASK)
            return hour, 1 if hour >= 12 else 0

        period = 1 if (raw_value & HR_PM_MASK) else 0
        hour = self.bcdToDec(raw_value & HR_12H_MASK)
        if hour == 12:
            hour = 0
        if period:
            hour += 12
        return hour, period

    def updateTime(self):
        if not self._active or not self._validate_time_fields():
            return False

        payload = (
            self.decToBcd(self.secondValue),
            self.decToBcd(self.minuteValue),
            self._encode_hour(self.hourValue, self.periodValue),
            self.decToBcd(self.dateValue),
            self.decToBcd(self.monthValue),
            self.decToBcd(self.yearValue),
            self.decToBcd(self.dayValue),
        )
        self.write_registers(ISL1208_SC, payload)
        return True

    def setTime(self, time_string):
        if not self._active or len(time_string) != 16 or not time_string.startswith("T") or not time_string.endswith("#"):
            return False

        payload = time_string[1:-1]
        try:
            self.yearValue = int(payload[0:2])
            self.monthValue = int(payload[2:4])
            self.dateValue = int(payload[4:6])
            self.hourValue = int(payload[6:8])
            self.minuteValue = int(payload[8:10])
            self.secondValue = int(payload[10:12])
            self.periodValue = int(payload[12:13])
            self.dayValue = int(payload[13:15])
        except ValueError:
            return False

        return self.updateTime()

    def updateAlarmTime(self):
        if not self._active or not self._validate_alarm_fields():
            return False

        payload = (
            ALARM_ENABLE_MASK | self.decToBcd(self.secondValueAlarm),
            ALARM_ENABLE_MASK | self.decToBcd(self.minuteValueAlarm),
            ALARM_ENABLE_MASK | self._encode_hour(self.hourValueAlarm, self.periodValueAlarm),
            ALARM_ENABLE_MASK | self.decToBcd(self.dateValueAlarm),
            ALARM_ENABLE_MASK | self.decToBcd(self.monthValueAlarm),
            self.decToBcd(self.dayValueAlarm),
        )
        self.write_registers(ISL1208_SCA, payload)
        return True

    def setAlarmTime(self, alarm_string):
        if not self._active or len(alarm_string) != 14 or not alarm_string.startswith("A") or not alarm_string.endswith("#"):
            return False

        payload = alarm_string[1:-1]
        try:
            self.monthValueAlarm = int(payload[0:2])
            self.dateValueAlarm = int(payload[2:4])
            self.hourValueAlarm = int(payload[4:6])
            self.minuteValueAlarm = int(payload[6:8])
            self.secondValueAlarm = int(payload[8:10])
            self.periodValueAlarm = int(payload[10:11])
            self.dayValueAlarm = int(payload[11:13])
        except ValueError:
            return False

        return self.updateAlarmTime()

    def fetchTime(self):
        if not self._active:
            return False

        try:
            data = self.read_registers(ISL1208_SC, ISL1208_DWA - ISL1208_SC + 1)
            self.secondValue = self.bcdToDec(data[ISL1208_SC] & 0x7F)
            self.minuteValue = self.bcdToDec(data[ISL1208_MN] & 0x7F)
            self.hourValue, self.periodValue = self._decode_hour(data[ISL1208_HR])
            self.dateValue = self.bcdToDec(data[ISL1208_DT] & 0x3F)
            self.monthValue = self.bcdToDec(data[ISL1208_MO] & 0x1F)
            self.yearValue = self.bcdToDec(data[ISL1208_YR])
            self.dayValue = self.bcdToDec(data[ISL1208_DW] & 0x07)

            self.secondValueAlarm = self.bcdToDec(data[ISL1208_SCA] & 0x7F)
            self.minuteValueAlarm = self.bcdToDec(data[ISL1208_MNA] & 0x7F)
            self.hourValueAlarm, self.periodValueAlarm = self._decode_hour(data[ISL1208_HRA] & 0xBF)
            self.dateValueAlarm = self.bcdToDec(data[ISL1208_DTA] & 0x7F)
            self.monthValueAlarm = self.bcdToDec(data[ISL1208_MOA] & 0x7F)
            self.dayValueAlarm = self.bcdToDec(data[ISL1208_DWA] & 0x7F)
            return True
        except Exception:
            return False

    def getHour(self):
        self.fetchTime()
        return self.hourValue

    def getMinute(self):
        self.fetchTime()
        return self.minuteValue

    def getSecond(self):
        self.fetchTime()
        return self.secondValue

    def getPeriod(self):
        self.fetchTime()
        return self.periodValue

    def getDay(self):
        self.fetchTime()
        return self.dayValue

    def getDate(self):
        self.fetchTime()
        return self.dateValue

    def getMonth(self):
        self.fetchTime()
        return self.monthValue

    def getYear(self):
        self.fetchTime()
        return self.yearValue

    def getAlarmHour(self):
        self.fetchTime()
        return self.hourValueAlarm

    def getAlarmMinute(self):
        self.fetchTime()
        return self.minuteValueAlarm

    def getAlarmSecond(self):
        self.fetchTime()
        return self.secondValueAlarm

    def getAlarmPeriod(self):
        self.fetchTime()
        return self.periodValueAlarm

    def getAlarmDay(self):
        self.fetchTime()
        return self.dayValueAlarm

    def getAlarmDate(self):
        self.fetchTime()
        return self.dateValueAlarm

    def getAlarmMonth(self):
        self.fetchTime()
        return self.monthValueAlarm

    def getTimeString(self):
        return "{}:{}:{} {}".format(
            self.getHour(),
            self.getMinute(),
            self.getSecond(),
            "PM" if self.getPeriod() else "AM",
        )

    def getDateString(self):
        return "{}-{}-{}".format(
            self.getDate(),
            self.getMonth(),
            self.getYear() + 2000,
        )

    def getDayString(self, n=None):
        day_name = self.DAY_NAMES[(self.getDay() + self.startOfTheWeek) % 7]
        if n is None:
            return day_name
        return day_name[:n]

    def getAlarmDayString(self, n=None):
        day_name = self.DAY_NAMES[(self.getAlarmDay() + self.startOfTheWeek) % 7]
        if n is None:
            return day_name
        return day_name[:n]

    def getDateDayString(self, n=None):
        day_name = self.getDayString(n)
        return "{}, {}".format(self.getDateString(), day_name)

    def getTimeDateString(self):
        return "{}, {}".format(self.getTimeString(), self.getDateString())

    def getTimeDateDayString(self, n=None):
        day_name = self.getDayString(n)
        return "{}, {}, {}".format(self.getTimeString(), self.getDateString(), day_name)

    def printTime(self):
        if not self.fetchTime():
            return False
        print(self.getTimeDateDayString())
        return True

    def printAlarmTime(self):
        if not self.fetchTime():
            return False
        print(
            "{}:{}:{} {}, {}-{} Every year, {}".format(
                self.hourValueAlarm,
                self.minuteValueAlarm,
                self.secondValueAlarm,
                "PM" if self.periodValueAlarm else "AM",
                self.dateValueAlarm,
                self.monthValueAlarm,
                self.getAlarmDayString(),
            )
        )
        return True

    def read_status(self):
        return self.read_register(ISL1208_SR)

    def read_interrupt_control(self):
        return self.read_register(ISL1208_INT)

    def set_frequency_output(self, fo_bits, enable_in_battery_backup=True):
        if not 0 <= fo_bits <= 0x0F:
            raise ValueError("FO value must be 0-15")
        current = self.read_interrupt_control()
        updated = current & 0xF0
        if not enable_in_battery_backup:
            updated |= 0x08
        updated |= fo_bits
        self.write_register(ISL1208_INT, updated)
        return self.read_interrupt_control()

    def set_fout_32768(self):
        return self.set_frequency_output(0x01)

    def check_battery(self):
        sr = self.read_status()
        return {
            "battery_low": (sr >> 4) & 0x01,
            "battery_mode": (sr >> 3) & 0x01,
        }

    def read_atr(self):
        return self.read_register(ISL1208_ATR)

    def set_atr(self, value):
        if not 0 <= value <= 0x3F:
            raise ValueError("ATR value must be 0-63")
        self.write_register(ISL1208_ATR, value)
        return self.read_atr()

    def read_dtr(self):
        return self.read_register(ISL1208_DTR)

    def set_dtr(self, value):
        if not 0 <= value <= 0x07:
            raise ValueError("DTR value must be 0-7")
        self.write_register(ISL1208_DTR, value)
        return self.read_dtr()

    def read_time(self):
        if not self.fetchTime():
            raise OSError("Failed to read RTC time")
        return (
            self.yearValue + 2000,
            self.monthValue,
            self.dateValue,
            self.hourValue,
            self.minuteValue,
            self.secondValue,
            self.dayValue,
        )

    def set_time(self, year, month, day, hour, minute, second, weekday=0):
        self.yearValue = year % 100
        self.monthValue = month
        self.dateValue = day
        self.hourValue = hour
        self.minuteValue = minute
        self.secondValue = second
        self.dayValue = weekday
        self.periodValue = 1 if hour >= 12 else 0
        if not self.updateTime():
            raise ValueError("Invalid RTC time values")

    def get_datetime_str(self):
        year, month, day, hour, minute, second, _ = self.read_time()
        return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            year, month, day, hour, minute, second
        )


RTCISL1208 = ISL1208RTC


if __name__ == "__main__":
    rtc = ISL1208RTC()
    print("RTC test start")
    print("r: read current time")
    print("a15: set ATR to 15")
    print("d2: set DTR to 2")
    print("f out: set FOUT to 32768Hz")
    print("q: quit")

    try:
        while True:
            cmd = input("cmd: ").strip().lower()
            if not cmd:
                continue

            if cmd == "q":
                break

            if cmd == "r":
                try:
                    print("time:", rtc.get_datetime_str())
                    print("atr:", rtc.read_atr())
                    print("dtr:", rtc.read_dtr())
                except Exception as exc:
                    print("read error:", exc)
                continue

            if cmd.startswith("a"):
                try:
                    atr_value = int(cmd[1:])
                    written = rtc.set_atr(atr_value)
                    print("atr set:", written)
                except ValueError:
                    print("invalid ATR value. use a0~a63")
                except Exception as exc:
                    print("atr write error:", exc)
                continue

            if cmd.startswith("d"):
                try:
                    dtr_value = int(cmd[1:])
                    written = rtc.set_dtr(dtr_value)
                    print("dtr set:", written)
                except ValueError:
                    print("invalid DTR value. use d0~d7")
                except Exception as exc:
                    print("dtr write error:", exc)
                continue

            if cmd == "f out":
                try:
                    written = rtc.set_fout_32768()
                    print("fout set to 32768Hz, int:", written)
                except Exception as exc:
                    print("fout write error:", exc)
                continue

            print("unknown command")
    except KeyboardInterrupt:
        print("exit")
