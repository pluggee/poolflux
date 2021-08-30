#!/usr/bin/python3

import time
import board
import adafruit_dht
from datetime import datetime
from influxdb import InfluxDBClient
import os

# Initial the dht device, with data pin connected to:
#dhtDevice = adafruit_dht.DHT22(board.D23, use_pulseio=False)
dhtDevice = adafruit_dht.DHT22(board.D23)

USER = 'admin'
PASSWORD = 'XXXX'
DBNAME = 'attic'
HOST = '10.0.1.30'
PORT = 8086
POLLTIME = 5

turn_on_temp = 37
turn_off_temp = 35
vue_username = 'sherif.eid@gmail.com'
vue_password = '*'
vue_tokenfile = '/tmp/vue_tokens.json'
attic_outlet_on = -1
# -1 : undefined
#  0 : off
#  1 : on

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
            print('Turning off attic fan')
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
            print('Turning on attic fan')
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
    print('Removing token file')
    os.remove(vue_tokenfile)
except:
    print('Trouble removing vue token file')

while True:
    cpu_temp = get_cpu_temp()
    try:
        print('attic_outlet_on = ' + str(attic_outlet_on))
        # Print the values to the serial port
        temperature_c = dhtDevice.temperature
        if (temperature_c > turn_on_temp):
            if (attic_outlet_on != 1):
                print('Attic is heating up')
                turn_on_attic_fan()

        if (temperature_c <= turn_off_temp):
            if (attic_outlet_on != 0):
                print('Attic is now cool')
                turn_off_attic_fan()
        
        temperature_f = temperature_c * (9 / 5) + 32
        humidity = dhtDevice.humidity
        current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        points = []
        point = {
            "measurement": 'Attic Temperature',
            "time": current_time,
            "fields": {
                "value": temperature_c
            }
        }
        points.append(point)
        point = {
            "measurement": 'Attic Humidity',
            "time": current_time,
            "fields": {
                "value": humidity
            }
        }
        points.append(point)
        
        point = {
            "measurement": 'CPU Temperature',
            "time": current_time,
            "fields": {
                "value": cpu_temp
            }
        }
        points.append(point)
       
        point = {
            "measurement": 'Attic FAN State',
            "time": current_time,
            "fields": {
                "value": attic_outlet_on
            }
        }
        points.append(point)

        print ('push to DB, Temp = ' + str(temperature_c) + ' humidity = ' + str(humidity) + ' cputemp = ' + str(cpu_temp))
        client = InfluxDBClient(HOST, PORT, USER, PASSWORD, DBNAME)
        client.switch_database(DBNAME)
        client.write_points(points)

    except RuntimeError as error:
        # Errors happen fairly often, DHT's are hard to read, just keep going
        print(error.args[0])
        time.sleep(POLLTIME)
        continue
    except Exception as error:
        dhtDevice.exit()
        raise error

    time.sleep(POLLTIME)
