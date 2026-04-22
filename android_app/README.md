# GSWater Android App

This Android app connects to the Pico 2W over BLE using Nordic UART Service.

## Features

- Scan and connect to `GSWater`
- Send all config values in one JSON payload
- Sync phone time to the board RTC with one button
- Show the latest BLE response and a simple TX/RX log

## Open In Android Studio

1. Open the `android_app` folder in Android Studio
2. Let Gradle sync
3. Run on an Android phone with BLE

## BLE messages used

- Config update:
  `{"SET_STOP_LEVEL_TXT":"80","SET_RUN_LEVEL_TXT":"60"}`
- RTC sync:
  `{"command":"sync_time","datetime":"2026-03-31 14:25:00"}`

## Notes

- Android 12+ needs `BLUETOOTH_SCAN` and `BLUETOOTH_CONNECT`
- Android 11 and below also need location permission for BLE scan
