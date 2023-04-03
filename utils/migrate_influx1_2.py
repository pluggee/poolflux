from influxdb import InfluxDBClient as InfluxDBClient15
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import sys
import json
import logging
import coloredlogs
import rich
import rich.progress
import signal
import time

coloredlogs.install(level='INFO')

if len(sys.argv) > 1:
    json_filename = sys.argv[1]
    logging.info('json file is {}'.format(json_filename))
    with open(json_filename, 'r') as f:
        input_dict = json.load(f)
else:
    logging.error("must have a json argument to tell the script what to do")
    sys.exit()


db15_host = input_dict["auth"]["db15_host"]
db15_port = input_dict["auth"]["db15_port"]
db15_db = input_dict["auth"]["db15_db"]
db15_un = input_dict["auth"]["db15_un"]
db15_pw = input_dict["auth"]["db15_pw"]
db2_url = input_dict["auth"]["db2_url"]
db2_token = input_dict["auth"]["db2_token"]
db2_org = input_dict["auth"]["db2_org"]
db2_bucket = input_dict["auth"]["db2_bucket"]

logging.info("Migration authentication:\n{}".format(
    json.dumps(input_dict["auth"], indent=4)))


for p2migrate in input_dict["migration"]:
    logging.info("Migrating:\n{}".format(json.dumps(p2migrate, indent=4)))

    # Connect to InfluxDB 1.5
    client15 = InfluxDBClient15(
        host=db15_host, port=db15_port, username=db15_un, password=db15_pw)
    client15.switch_database(db15_db)

    # Query the total number of points in the measurement
    meas15 = p2migrate["db15_meas"]
    field15 = p2migrate["db15_field"]
    meas2 = p2migrate["db2_meas"]
    field2 = p2migrate["db2_field"]

    count_query = f'SELECT COUNT(*) FROM "{meas15}"'
    count_result = client15.query(count_query)

    # Extract the total number of points from the result
    total_points = 0
    for point_count in count_result.get_points():
        for key, value in point_count.items():
            if key.lower() != 'time':
                total_points += value

    logging.info("Measurement {} has {} points".format(meas15, total_points))

    # Connect to InfluxDB 2.6
    client2 = InfluxDBClient(url=db2_url, token=db2_token, org=db2_org)
    write_api = client2.write_api(write_options=SYNCHRONOUS)

    # Query and transfer data in chunks of 1000 points
    chunk_size = p2migrate["chunk"]
    offset = p2migrate["offset"]
    logging.info("Starting to migrate from offset {}".format(offset))

    try:
        with rich.progress.Progress() as progress:
            task = progress.add_task("[cyan]Migrating ({},{}) -> ({},{})...".format(
                meas15, field15, meas2, field2), total=total_points)
            progress.update(task, advance=offset)

            while True:
                # Query data from InfluxDB 1.5
                query = f'SELECT * FROM "{meas15}" LIMIT {chunk_size} OFFSET {offset}'
                ts = time.monotonic()
                result_set = client15.query(query)
                te = time.monotonic()
                tq = round(te - ts, 2)

                if not result_set:
                    break

                points = []

                # Write data to InfluxDB 2.6
                ts = time.monotonic()
                for result in result_set:
                    for record in result:
                        point = Point(meas2)
                        point.field(field2, record[field15])
                        if (field2 == 'temp_c'):
                            temp_f = record[field15]*1.8 + 32
                            point.field('temp_f', temp_f)
                        point.time(record["time"])
                        points.append(point)
                te = time.monotonic()
                tp = round(te - ts, 2)

                ts = time.monotonic()
                write_api.write(bucket=db2_bucket, record=points)
                te = time.monotonic()
                tw = round(te - ts, 2)

                # Update the offset
                offset += chunk_size
                num_str = "{:>11d}".format(offset)
                progress.update(task, advance=chunk_size)
                logging.info(
                    "{}/{} migrated --- times {}/{}/{}".format(num_str, total_points, tq, tp, tw))
                time.sleep(1)

    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt. Exiting...")

    # Close the connections
    client15.close()
    client2.__del__()
