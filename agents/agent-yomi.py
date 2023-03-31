#!/usr/bin/env python3
import sys
from datetime import datetime
import time
from sensirion_i2c_driver import I2cConnection, LinuxI2cTransceiver
from sensirion_i2c_sen5x import Sen5xI2cDevice
import signal
import logging
import logging.handlers
import coloredlogs
import json
import os
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

import requests
print(requests.certs.where())

# You can generate an API token from the "API Tokens Tab" in the UI
token = os.getenv("INFLUX_TOKEN")
org = "home"
bucket = "yomi"

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

logging.info('token: {}'.format(token))

with LinuxI2cTransceiver('/dev/i2c-1') as i2c_transceiver:
    device = Sen5xI2cDevice(I2cConnection(i2c_transceiver))

    # Print some device information
    logging.info("Version: {}".format(device.get_version()))
    logging.info("Product Name: {}".format(device.get_product_name()))
    logging.info("Serial Number: {}".format(device.get_serial_number()))

    # Perform a device reset (reboot firmware)
    device.device_reset()

    # Start measurement
    device.start_measurement()

    try: 
        while(run_loop):
            # Wait until next result is available
            logging.debug("Waiting for new data...")
            while device.read_data_ready() is False:
                time.sleep(0.1)
            
            store = False
            # Read measured values -> clears the "data ready" flag
            values = device.read_measured_values()

            current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            point = Point("YomiSEN55")
            point.time(datetime.utcnow(), WritePrecision.NS)

            if (values.mass_concentration_1p0.available):
                if (values.mass_concentration_1p0.physical != 0.0):
                    point.field("mc1p0", values.mass_concentration_1p0.physical)
                    store = True
            if (values.mass_concentration_1p0.available):
                if (values.mass_concentration_2p5.physical != 0.0):
                    point.field('mc2p5', values.mass_concentration_2p5.physical)
                    store = True
            if (values.mass_concentration_1p0.available):
                if (values.mass_concentration_4p0.physical != 0.0):
                    point.field('mc4p0', values.mass_concentration_4p0.physical)
                    store = True
            if (values.mass_concentration_1p0.available):
                if (values.mass_concentration_10p0.physical != 0.0):
                    point.field('mc10p0', values.mass_concentration_10p0.physical)
                    store = True

            if (values.ambient_humidity.available):
                point.field('rh', values.ambient_humidity.percent_rh)
                store = True

            if (values.ambient_temperature.available):
                point.field('temp_c', values.ambient_temperature.degrees_celsius)
                point.field('temp_f', values.ambient_temperature.degrees_fahrenheit)
                store = True

            if (values.voc_index.available):
                point.field('voc_index', values.voc_index.scaled)
                store = True

            if (values.nox_index.available):
                point.field('nox_index', values.nox_index.scaled)
                store = True

            logging.debug('values: \n{}'.format(values))

            if (store):
                logging.info('push to influxDB2')
                with InfluxDBClient(url="https://influx.elnamla.com:8086", token=token, org=org) as client:
                    write_api = client.write_api(write_options=SYNCHRONOUS)
                    write_api.write(bucket, org, point)
                client.close()

            # Read device status
            status = device.read_device_status()
            logging.info("Device Status: {}".format(status))

    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt. Exiting...")

    # Stop measurement
    device.stop_measurement()
    logging.info("Measurement stopped.")

