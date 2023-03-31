#!/usr/bin/python3
import logging
import coloredlogs
import time
import board
import adafruit_dht
from datetime import datetime
import os, sys
import signal
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import logging.handlers

influx_token = os.getenv("INFLUX_TOKEN")
org = "home"
bucket = "attic"

# Initial the dht device, with data pin connected to:
dhtDevice = adafruit_dht.DHT22(board.D23)

POLLTIME = 5

turn_on_temp = 37
turn_off_temp = 35
vue_username = 'sherif.eid@gmail.com'
vue_password = 'SH6hU666v2Mw#n!'
vue_tokenfile = '/tmp/vue_tokens.json'
attic_outlet_on = -1
# -1 : undefined
#  0 : off
#  1 : on

# check if first argument exists, will be the config file
log_filename = 'mylog.log'
if len(sys.argv) > 1:
    log_filename = sys.argv[1]
    print('logging output to {}'.format(log_filename))

run_loop = True
def handle_sigterm(signum, frame):
    global run_loop
    run_loop = False

signal.signal(signal.SIGTERM, handle_sigterm)

# Set up logging to a file with size limitation and rotation
max_bytes = 10000000  # 10 MB
backup_count = 5  # Keep up to 5 old log files
file_handler = logging.handlers.RotatingFileHandler(
    log_filename, maxBytes=max_bytes, backupCount=backup_count)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
logging.getLogger().addHandler(file_handler)

coloredlogs.install(level='INFO')
logging.info('influx_token: {}'.format(influx_token))

def turn_off_attic_fan():
    import pyemvue
    global attic_outlet_on
    global vue_username, vue_password, vue_tokenfile
    vue = pyemvue.PyEmVue()
    vue.login(username=vue_username, password=vue_password, token_storage_file=vue_tokenfile)
    attic_gid = 41020
    devices = vue.get_devices()
    for device in devices:
        vue.populate_device_properties(device)
        if (device.device_gid == attic_gid):
            logging.info('Turning off attic fan')
            device.outlet.outlet_on = False
            device.outlet = vue.update_outlet(device.outlet)
            attic_outlet_on = 0

def turn_on_attic_fan():
    import pyemvue
    global attic_outlet_on
    global vue_username, vue_password, vue_tokenfile
    vue = pyemvue.PyEmVue()
    vue.login(username=vue_username, password=vue_password, token_storage_file=vue_tokenfile)
    attic_gid = 41020
    devices = vue.get_devices()
    for device in devices:
        vue.populate_device_properties(device)
        if (device.device_gid == attic_gid):
            logging.info('Turning on attic fan')
            device.outlet.outlet_on = True
            device.outlet = vue.update_outlet(device.outlet)
            attic_outlet_on = 1


def get_cpu_temp():
    tFile = open('/sys/class/thermal/thermal_zone0/temp')
    temp = float(tFile.read())
    tempC = temp/1000
    return tempC


# file clean up
try:
    logging.info('Removing vue token file')
    os.remove(vue_tokenfile)
except:
    logging.warning('Trouble removing vue token file')

while True:
    cpu_temp = get_cpu_temp()
    try:
        # Print the values to the serial port
        temperature_c = dhtDevice.temperature
        temperature_f = temperature_c * (9 / 5) + 32
        humidity = dhtDevice.humidity
        current_time = datetime.utcnow()
        timenow = current_time
        point_dht22 = Point("DHT22")
        point_dht22.time(current_time, WritePrecision.NS)
        point_dht22.field("temp_c", temperature_c)
        point_dht22.field("temp_f", temperature_f)
        point_dht22.field("rh", humidity)

        point_cpu = Point("CPU")
        point_cpu.time(current_time, WritePrecision.NS)
        point_cpu.field("temp_c", cpu_temp)

        point_fan = Point("FAN")
        point_fan.time(current_time, WritePrecision.NS)
        point_fan.field("state", attic_outlet_on)

        logging.info('push to DB, Temp = ' + str(temperature_c) + ' humidity = ' + str(humidity) + ' cputemp = ' + str(cpu_temp))
        with InfluxDBClient(url="https://influx.elnamla.com:8086", token=influx_token, org=org) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket, org, point_dht22)
            write_api.write(bucket, org, point_cpu)
            write_api.write(bucket, org, point_fan)
        client.close()
        
        logging.info('attic_outlet_on = ' + str(attic_outlet_on))
        if (temperature_c > turn_on_temp):
            if (attic_outlet_on != 1):
                logging.warning('Attic is heating up')
                turn_on_attic_fan()

        if (temperature_c <= turn_off_temp):
            if (attic_outlet_on != 0):
                logging.info('Attic is now cool')
                turn_off_attic_fan()
        
    except RuntimeError as error:
        # Errors happen fairly often, DHT's are hard to read, just keep going
        logging.error(error.args[0])
        time.sleep(POLLTIME)
        continue
    except Exception as error:
        dhtDevice.exit()
        raise error

    time.sleep(POLLTIME)
