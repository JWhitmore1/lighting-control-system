# lighting-control-system
A Live Lighting Effects Control system for Magic Home Smart Bulbs/LED Strips.  
Triggers effects on a consistent BPM, accounting for API latency/sync issues.  
CLI Supports bpm tapping to schedule lighting changes on beats (or manually set bpm).  
Setup effects like colour swells, fades and transitions between colours as well as a strobe toggle + many other controls for live lighting.  

## Setup
### Device Setup
First setup your Smart Device using the Magic Home Pro app.  
note: for this setup, you do **not** need to give the app your location permissions, and you do **not** need to make an account.


Much of the setup can be skipped, just ensure the smart device is connected to the network you wish to run this from.

### API Setup
Follow setup instructions for [magic-home-rest](https://github.com/CasperVerswijvelt/magic-home-rest), this will host the API used for communicating with the smart device

### Script setup
 1. Install dependencies
 2. Using [magic-home-rest](https://github.com/CasperVerswijvelt/magic-home-rest) find the id of your device.
 3. Update the global variables with your `device id` and the `local address` your API is hosting to.
```
BASE_URL = "<your api address>"
DEVICE_ID = "<your device id>"
```

## Running
1. Start [magic-home-rest](https://github.com/CasperVerswijvelt/magic-home-rest) API
2. Ensure Smart Device is detected
3. Run script
```
python lighting-control-cli.py
```
if using a virtual environment
```
/venv/bin/python lighting-control-cli.py
```
