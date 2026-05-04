import time
from machine import WDT, reset_cause


WATCHDOG_TIMEOUT_MS = 8000
FEED_SECONDS = 5
WAIT_SECONDS = 15


def sleep_one_second():
    try:
        time.sleep_ms(1000)
    except AttributeError:
        time.sleep(1)


def main():
    print("reset_cause:", reset_cause())
    print("creating WDT timeout={} ms".format(WATCHDOG_TIMEOUT_MS))

    try:
        wdt = WDT(timeout=WATCHDOG_TIMEOUT_MS)
    except Exception as exc:
        print("WDT create failed:", exc)
        return

    print("WDT create ok")
    print("feeding for {} seconds...".format(FEED_SECONDS))
    for second in range(FEED_SECONDS):
        wdt.feed()
        print("fed:", second + 1)
        sleep_one_second()

    print("stopping feed now")
    print("if 8s timeout works, board should reset before {} seconds pass".format(WAIT_SECONDS))
    for second in range(WAIT_SECONDS):
        print("waiting without feed:", second + 1)
        sleep_one_second()

    print("no reset happened within wait window")


main()
