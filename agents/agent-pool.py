#!/usr/bin/python3
import logging
import coloredlogs
import serial
import time
from datetime import datetime
from influxdb import InfluxDBClient
from AtlasI2C import (
    AtlasI2C
)
import os
import sys
import signal
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import logging.handlers

# USER = 'admin'
# PASSWORD = 'XXXX'
# DBNAME = 'pool'
# HOST = 'localhost'
# PORT = 8086
POLLTIME = 10

ser = serial.Serial('/dev/ttyACM0', timeout=1)  # open serial port

influx_token = os.getenv("INFLUX_TOKEN")
org = "home"
bucket = "pool"

# check if first argument exists, will be the config file
log_filename = 'mylog.log'
if len(sys.argv) > 1:
    log_filename = sys.argv[1]
    print('logging output to {}'.format(log_filename))

run_loop = True


def handle_sigterm(signum, frame):
    global run_loop
    run_loop = False
    logging.info('Received termination signal {}'.format(signum))


signal.signal(signal.SIGTERM, handle_sigterm)

# Set up logging to a file with size limitation and rotation
max_bytes = 10000000  # 10 MB
backup_count = 5  # Keep up to 5 old log files
file_handler = logging.handlers.RotatingFileHandler(
    log_filename, maxBytes=max_bytes, backupCount=backup_count)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s'))
logging.getLogger().addHandler(file_handler)


def get_devices():
    device = AtlasI2C()
    device_address_list = device.list_i2c_devices()
    device_list = []

    for i in device_address_list:
        device.set_i2c_address(i)
        response = device.query("I")
        moduletype = response.split(",")[1]
        response = device.query("name,?").split(",")[1]
        device_list.append(
            AtlasI2C(address=i, moduletype=moduletype, name=response))
    return device_list


def print_devices(device_list, device):
    for i in device_list:
        if (i == device):
            logging.info("--> " + i.get_device_info())
        else:
            logging.info(" - " + i.get_device_info())


def get_cpu_temp():
    tFile = open('/sys/class/thermal/thermal_zone0/temp')
    temp = float(tFile.read())
    tempC = temp/1000
    return tempC


def push_datapoint(ORP, Temperature, pH, waterlevel):
    current_time = datetime.utcnow()
    logging.info('timestamp : ' + current_time)

    point_pool = Point("pool")
    point_pool.time(current_time, WritePrecision.NS)
    point_pool.field("ORP", ORP)
    point_pool.field("temp_c", Temperature)
    point_pool.field("temp_f", (Temperature * 1.8) + 32)
    point_pool.field("pH", pH)
    point_pool.field("Water Level", waterlevel)
    cpu_temp = get_cpu_temp()
    point_cpu = Point("host")
    point_cpu.time(current_time, WritePrecision.NS)
    point_cpu.field("cpu_temp_c", cpu_temp)
    logging.info('pushing to DB ORP = ' + str(ORP) + ' Temperature = ' +
                 str(Temperature) + ' pH = ' + str(pH))

    with InfluxDBClient(url="https://influx.elnamla.com:8086", token=influx_token, org=org) as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket, org, [point_pool, point_cpu])
    client.close()


def main():
    global run_loop
    device_list = get_devices()
    device = device_list[0]
    print_devices(device_list, device)

    try:
        while run_loop:
            for dev in device_list:
                dev.write("R")
            time.sleep(POLLTIME)
            rawstr = device_list[0].read().split(' ')
            v_ORP = float(rawstr[4].rstrip('\x00'))
            rawstr = device_list[1].read().split(' ')
            v_pH = float(rawstr[4].rstrip('\x00'))
            rawstr = device_list[2].read().split(' ')
            v_Temperature = float(rawstr[4].rstrip('\x00'))
            raw_waterlevel = float(
                ser.readline().decode("utf-8").rstrip().lstrip())
            waterlevel = raw_waterlevel*2/(-66) + 3.8 + 666/66
            push_datapoint(v_ORP, v_Temperature, v_pH, waterlevel)

    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")

    logging.info('Measurement stopped, exiting ...')


if __name__ == '__main__':
    coloredlogs.install(level='INFO')
    logging.info('--- Starting Pool logger ---')
    logging.info('influx_token: {}'.format(influx_token))
    main()
