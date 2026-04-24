import math
import time
from machine import ADC, Pin

from dgus_control_pico import DgusControl


VP_CSV_PATH = "dgus_vp_list.CSV"

# ADC 설정 (ADC0, GP26)
adc = ADC(Pin(26))


def read_rms_current():
    # 1kHz 샘플링, 0.2초 (200 샘플)
    samples = 200
    delay = 0.001
    sum_sq = 0.0

    for _ in range(samples):
        raw = adc.read_u16()
        voltage = (raw / 65535) * 3.3
        voltage_ac = voltage - 1.65
        sum_sq += voltage_ac ** 2
        time.sleep(delay)

    rms_voltage = math.sqrt(sum_sq / samples)
    rms_current = rms_voltage * 50
    return rms_current


def split_csv_line(line):
    fields = []
    current = []
    in_quotes = False

    for char in line:
        if char == '"':
            in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            fields.append("".join(current).strip())
            current = []
        else:
            current.append(char)

    fields.append("".join(current).strip())
    return fields


def load_vp_entries(csv_path=VP_CSV_PATH):
    entries = []

    with open(csv_path, "r") as handle:
        header_skipped = False
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if not header_skipped:
                header_skipped = True
                continue

            fields = split_csv_line(line)
            if len(fields) < 6:
                continue

            page_text, name, vp_text, example, length_text, description = fields[:6]

            try:
                page = int(page_text)
                vp = int(vp_text, 16)
            except ValueError:
                continue

            try:
                length = int(length_text) if length_text else 0
            except ValueError:
                length = 0

            entries.append(
                {
                    "page": page,
                    "name": name,
                    "vp": vp,
                    "example": example,
                    "length": length,
                    "description": description,
                }
            )

    return entries


def get_entries_for_page(page, csv_path=VP_CSV_PATH):
    return [entry for entry in load_vp_entries(csv_path) if entry["page"] == page]


def parse_numeric_example(example):
    text = example.strip()
    if not text:
        return 0
    if "~" in text:
        text = text.split("~", 1)[0].strip()
    if "," in text:
        text = text.split(",", 1)[0].strip()
    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1].strip()
    return int(text)


def build_text_value(entry):
    name = entry["name"]
    if name == "CURRENT_TXT":
        return "{:.2f}A".format(read_rms_current())

    text = entry["example"] or name
    if entry["length"] > 0:
        return text[: entry["length"]]
    return text


def write_entry(display, entry):
    description = entry["description"].lower()

    if "text" in description:
        value = build_text_value(entry)
        response = display.set_text(entry["vp"], value, encoding="ascii")
        print(
            "TEXT page={} vp=0x{:04X} name={} value={!r} resp={}".format(
                entry["page"],
                entry["vp"],
                entry["name"],
                value,
                response.hex(" "),
            )
        )
        return

    value = parse_numeric_example(entry["example"])
    response = display.set_vp(entry["vp"], value)
    print(
        "VAR  page={} vp=0x{:04X} name={} value={} resp={}".format(
            entry["page"],
            entry["vp"],
            entry["name"],
            value,
            response.hex(" "),
        )
    )


def prompt_page(pages):
    while True:
        selected = input("Select page {}: ".format(pages)).strip()
        try:
            page = int(selected)
        except ValueError:
            print("숫자로 입력하세요.")
            continue

        if page not in pages:
            print("목록에 있는 페이지를 선택하세요.")
            continue
        return page


def test_display_page():
    entries = load_vp_entries()
    if not entries:
        print("CSV에서 VP 목록을 읽지 못했습니다.")
        return

    pages = sorted({entry["page"] for entry in entries})
    page = prompt_page(pages)
    page_entries = [entry for entry in entries if entry["page"] == page]

    if not page_entries:
        print("선택한 페이지에 VP가 없습니다.")
        return

    display = DgusControl()
    try:
        display.set_page(page)
        print("PAGE={} VP_COUNT={}".format(page, len(page_entries)))
        time.sleep(0.2)

        for entry in page_entries:
            write_entry(display, entry)
            time.sleep(0.05)

        print("페이지 {} 테스트 완료".format(page))
    finally:
        display.close()


if __name__ == "__main__":
    test_display_page()
