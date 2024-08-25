# -*- coding: utf-8 -*-

"""
Originally Created by Sara Geleskie Damiano on 1/9/2017
Modified by Matt Findley April 2021 to work with Python 3,
only modified slightly:
 - adding parentheses to the Python 2 print statements.
 - replacing raw_input() functions with input() functions.
 - using f-strings to assemble strings of text and variables.
 - info about serial devices accessed via object attributes rather than position in a tuple.
 - convert Python3 unicode strings to bytestrings (and visa versa) so that we can read/write data
   on serial port.

This program interacts with an FTDI connected Arduino device (like the EnviroDIY Mayfly)
running sync_clock_PC.ino to synchronize the RTC chip to Network Time Protocol clocks
(or to local PC time is NTP is unavailable)
"""

# %%
from datetime import datetime, timezone, timedelta
import time

import ntplib
import serial.tools.list_ports


# %%
def get_device_time():
    # A helper function to get the current time from a device running sync_clock_PC.ino
    device_time_str = device.readline().decode()
    print("<<<" + device_time_str, end="")
    device_rtc = int(device_time_str.split("(")[1].split(")")[0])
    return device_rtc


def get_pc_time(tz_offset=0, notifications=False):
    # A helper function to get the current time of either the PC or the US national time protocol servers
    # Checks for internet connection and if that is available returns the US NTP time, otherwise it
    # returns the local PC clock time.
    # Returns the current time (localized to the current PC) as a unix timestamp

    try:
        c = ntplib.NTPClient()
        response = c.request("us.pool.ntp.org", version=3)
        utc_unix_time = response.orig_time
        if notifications:
            print(
                f"Using time from Network Time Protocol server us.pool.ntp.org: {utc_unix_time} ({datetime.fromtimestamp(utc_unix_time, tz=timezone.utc).isoformat()})"
            )
    except:
        ts_utc = datetime.now(timezone.utc)
        utc_unix_time = (
            ts_utc - datetime(1970, 1, 1, tzinfo=timezone.utc)
        ).total_seconds()
        if notifications:
            print(f"Using local computer time: {utc_unix_time} ({ts_utc.isoformat()})")

    # Conversions to deal with local vs. UTC time
    if notifications:
        print(f"RTC chip is being set to UTC{tz_offset if tz_offset!=0 else''}")
        print("Please account for timezones in your sketch")
    # return int(utc_unix_time + (tz_offset * 3600))
    return int(utc_unix_time)


def parse_device_set_response():
    # Parses the device's response to the time-setting commands
    curr_repeat = "Current RTC Date/Time: "
    set_resp = "Current RTC Date/Time: "
    start = datetime.now()
    # clean out any pending output
    while set_resp.startswith(curr_repeat) and datetime.now() - start < timedelta(
        seconds=5
    ):
        set_resp = device.readline().decode()
        print("<<<" + set_resp, end="")

    # wait for the offset line
    start = datetime.now()
    while not set_resp.startswith("RTC is Off ") and datetime.now() - start < timedelta(
        seconds=5
    ):
        set_resp = device.readline().decode()
        print("<<<" + set_resp, end="")
    # get the offset from this line
    diffts_abs = int(set_resp.split()[4])

    # wait for the "Updating RTC line"
    start = datetime.now()
    while not set_resp.startswith(
        "Updating RTC"
    ) and datetime.now() - start < timedelta(seconds=5):
        set_resp = device.readline().decode()
        print("<<<" + set_resp, end="")

    # the line should now be `Updating RTC, old = # new = #`
    # parse the old and new time from this line
    oldts = int(set_resp.split()[7])
    newts = int(set_resp.split()[4])

    return oldts, newts, diffts_abs


# %%
# Check all available serial ports
ports = serial.tools.list_ports.comports()

# %%
# ask the user what com port to use
comport_num = input("Enter the number of the COM port, followed by enter key")

# Keep the port specified
device_ports = [p for p in ports if p.device == f"COM{comport_num}"]

# Give warnings if 0 or >1 Mayflies found
if not device_ports:
    print(f"No device found at COM{comport_num}")
    input("Press Enter to Exit")
    exit()
else:
    print(f"Device found at {device_ports[0].device}")
    print(device_ports[0].description)
    print(device_ports[0].hwid)

# Open up the device serial port
try:
    device = serial.Serial(device_ports[0].device, 57600, timeout=5)
except:
    print(f"Cannot access {device_ports[0].device}")
    print("Please close any other programs accessing the serial port")
    input("Press Enter to Exit")
    exit()

# %%
# Wait for the device to initialize
print("Waiting for device to initialize")
time.sleep(2)
timeout_time = time.time() + 10
device.flushInput()  # flush input buffer, discarding all its contents
device.flushOutput()  # flush output buffer, aborting current output and discard all that is in buffer
print()
print(f"<<< {device.readline().decode()}", end="")
print(f"<<< {device.readline().decode()}", end="")

# Check that getting expected responses from the device
try:
    get_device_time()
except:
    print("Device is not sending expected output.")
    print("Please ensure that sync_clock_PC.ino has been uploaded to the device")
    input("Press Enter to Exit")
    exit()

# %%
# ask the user what com port to use
print("I **VERY STRONGLY** recommend setting the offset to 0!!")
print("If you really want your RTC in a local zone enter it now")
print("For UTC use 0, for EST use -5")
tz_offset_hours = input("Enter the timezone offset from UTC in hours (0 recommended!)")
tz_offset_hours = int(tz_offset_hours)


# %%
# Send the time to the device
print("First attempt to set the clock")
run_time_check = datetime.now()
device.flushInput()  # flush input buffer, discarding all its contents
device.flushOutput()  # flush output buffer, aborting current output and discard all that is in buffer
unix_time_string = "T" + str(get_pc_time(tz_offset=tz_offset_hours, notifications=True))
device.write(unix_time_string.encode("utf-8"))
print(">>>" + unix_time_string)
mf_resp1 = parse_device_set_response()
print(f"Clock set to {mf_resp1[1]}")
set_time_check = (datetime.now() - run_time_check).total_seconds()
print(f"Setting the clock took {set_time_check} seconds")

# Send the time to the device again to double-check the offsets
print("Checking the device response offset")
device.flushInput()  # flush input buffer, discarding all its contents
device.flushOutput()  # flush output buffer, aborting current output and discard all that is in buffer
unix_time_string = "T" + str(get_pc_time(tz_offset=tz_offset_hours))
device.write(unix_time_string.encode("utf-8"))
print(">>>" + unix_time_string)
mf_resp2 = parse_device_set_response()

# Send the time to the device again adjusting for the offset
if mf_resp2[2] > 1:
    print(f"Device takes {mf_resp2[2]} seconds to respond to the PC time set command")
    print("Re-adjusting the device clock")
    device.flushInput()  # flush input buffer, discarding all its contents
    device.flushOutput()  # flush output buffer, aborting current output and discard all that is in buffer
    adjusted_unix_time_string = "T" + str(
        get_pc_time(tz_offset=tz_offset_hours) + int(set_time_check) + mf_resp2[2]
    )
    device.write(adjusted_unix_time_string.encode("utf-8"))
    print(">>>" + adjusted_unix_time_string)
else:
    print("Device responded in less than 1 second")
    print("Re-adjusting the device clock")
    device.flushInput()  # flush input buffer, discarding all its contents
    device.flushOutput()  # flush output buffer, aborting current output and discard all that is in buffer
    readjust_str = "T" + str(
        get_pc_time(tz_offset=tz_offset_hours) + int(set_time_check)
    )
    device.write(readjust_str.encode("utf-8"))
    print(">>>" + readjust_str)

print("Device RTC is now within 1 second of computer or NTP clock")
print("It is not possible to adjust the DS3231 to millisecond precision.")
print(f"<<< {device.readline().decode()}")

# %%
device.close()

# %%
input("Press Enter to Exit")
exit()
