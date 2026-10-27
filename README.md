# RS3 Buff Tracker

A small Windows companion toolkit for RuneScape 3. It uses read-only screen capture to look for selected buff icons; it does not read game memory or automate gameplay.

## First-time setup

1. Download this repository as a ZIP using **Code → Download ZIP**.
2. Extract the ZIP.
3. Double-click `run_toolkit.bat`. It installs Pillow if needed and starts the app.
4. Select the buff-bar region, add a buff, capture the preview, and select the icon from the preview.
5. Start monitoring.

## Updates

Click **Check for updates** inside the app. If a newer version is published in `version.json`, the app asks before installing it and restarts afterward. Your saved settings and icon templates are stored under your Windows user profile in `.runescape_toolkit` and are not replaced by app updates.

## Limitations

This is an early visual prototype. It alerts when an icon that was previously detected disappears; that can mean the buff expired, but a visual recognition miss can also trigger an alert. It does not yet read exact remaining buff duration.

Only install updates from this repository that you trust.
