#!/usr/bin/python3

import serial
import time
from datetime import datetime
from influxdb import InfluxDBClient
from AtlasI2C import (
	 AtlasI2C
)

USER = 'admin'
PASSWORD = 'XXXX'
DBNAME = 'pool'
HOST = 'localhost'
PORT = 8086
POLLTIME = 10

ser = serial.Serial('/dev/ttyACM0', timeout = 1)  # open serial port

def get_devices():
    device = AtlasI2C()
    device_address_list = device.list_i2c_devices()
    device_list = []

    for i in device_address_list:
        device.set_i2c_address(i)
        response = device.query("I")
        moduletype = response.split(",")[1]
        response = device.query("name,?").split(",")[1]
        device_list.append(AtlasI2C(address = i, moduletype = moduletype, name = response))
    return device_list

def print_devices(device_list, device):
    for i in device_list:
        if(i == device):
            print("--> " + i.get_device_info())
        else:
            print(" - " + i.get_device_info())

def get_cpu_temp():
    tFile = open('/sys/class/thermal/thermal_zone0/temp')
    temp = float(tFile.read())
    tempC = temp/1000
    return tempC

def push_datapoint(ORP, Temperature, pH, waterlevel):
    current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    print('timestamp : ' + current_time)
    points = []
    point = {
        "measurement": 'ORP',
        "time": current_time,
        "fields": {
            "value": ORP
        }
    }
    points.append(point)
    point = {
        "measurement": 'Temperature',
        "time": current_time,
        "fields": {
            "value": Temperature
        }
    }
    points.append(point)
    point = {
        "measurement": 'pH',
        "time": current_time,
        "fields": {
            "value": pH
        }
    }
    points.append(point)
    point = {
        "measurement": 'Water Level',
        "time": current_time,
        "fields": {
            "value": waterlevel 
        }
    }
    points.append(point)
    cpu_temp = get_cpu_temp()
    point = {
        "measurement": 'CPU Temperature',
        "time": current_time,
        "fields": {
            "value": cpu_temp
        }
    }
    points.append(point)
    print('pushing to DB ORP = ' + str(ORP) + ' Temperature = ' + str(Temperature) + ' pH = ' + str(pH))
    client = InfluxDBClient(HOST, PORT, USER, PASSWORD, DBNAME)
    client.switch_database(DBNAME)
    client.write_points(points)

def main():
    device_list = get_devices()
    device = device_list[0]
    print_devices(device_list, device)
    
    while True:
        for dev in device_list:
            dev.write("R")
        time.sleep(POLLTIME)
        rawstr = device_list[0].read().split(' ')
        v_ORP = float(rawstr[4].rstrip('\x00'))
        rawstr = device_list[1].read().split(' ')
        v_pH = float(rawstr[4].rstrip('\x00'))
        rawstr = device_list[2].read().split(' ')
        v_Temperature = float(rawstr[4].rstrip('\x00'))
        raw_waterlevel = float(ser.readline().decode("utf-8").rstrip().lstrip())
        waterlevel = raw_waterlevel*2/(-66) + 3.8 + 666/66
        push_datapoint(v_ORP, v_Temperature, v_pH, waterlevel)

if __name__ == '__main__':
    main()

