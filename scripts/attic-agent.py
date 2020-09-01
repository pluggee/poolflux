#!/usr/bin/python3

import time
import board
import adafruit_dht
from datetime import datetime
from influxdb import InfluxDBClient

# Initial the dht device, with data pin connected to:
#dhtDevice = adafruit_dht.DHT22(board.D23, use_pulseio=False)
dhtDevice = adafruit_dht.DHT22(board.D23)

USER = 'admin'
PASSWORD = 'XXXX'
DBNAME = 'attic'
HOST = '10.0.1.30'
PORT = 8086
POLLTIME = 5

def get_cpu_temp():
    tFile = open('/sys/class/thermal/thermal_zone0/temp')
    temp = float(tFile.read())
    tempC = temp/1000
    return tempC

while True:
    cpu_temp = get_cpu_temp()
    
    try:
        # Print the values to the serial port
        temperature_c = dhtDevice.temperature
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
