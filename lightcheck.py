#!/usr/bin/python3
#Output delay check test for TSL2561 Luminosity Sensor
#
# 1000 impulses / kWh
#
import smbus
import time
import signal
import sys
import paho.mqtt.client as mqtt
import logging

TSLaddr = 0x39 #Default I2C address, alternate 0x29, 0x49 
TSLcmd = 0x80 #Command
chan0 = 0x0C #Read Channel0 sensor date
chan1 = 0x0E #Read channel1 sensor data
TSLon = 0x03 #Switch sensors on
TSLoff = 0x00 #Switch sensors off
#Exposure settings
LowShort = 0x00 #x1 Gain 13.7 miliseconds
LowMed = 0x01 #x1 Gain 101 miliseconds
LowLong = 0x02 #x1 Gain 402 miliseconds
LowManual = 0x03 #x1 Gain Manual
HighShort = 0x10 #LowLight x16 Gain 13.7 miliseconds
HighMed = 0x11	#LowLight x16 Gain 100 miliseconds
HighLong = 0x12 #LowLight x16 Gain 402 miliseconds
HighManual = 0x13 #LowLight x16 Gain Manual
# Get I2C bus
bus = smbus.SMBus(1)
writebyte = bus.write_byte_data

logging.basicConfig(filename='lightcheck.log',level=logging.DEBUG)

class Data:
    def __init__(self, ch0, ch1):
        self.ch0 = ch0
        self.ch1 = ch1

def signal_handler(sig, frame):
        writebyte(TSLaddr, 0x00 | TSLcmd, TSLoff)
        client.publish("light/status/", "stopped at " + time.asctime(time.localtime(time.time())))
        logging.info('sensor deactivated')
        sys.exit(0)

# Register the SIGINT handler
signal.signal(signal.SIGINT, signal_handler)

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, rc):
    logging.info("Connected with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("$SYS/#")

client = mqtt.Client(client_id="light_reader", transport="tcp")
client.on_connect = on_connect

client.connect("diskstation", 1883, 60)
client.publish("light/status", "reading")

def publish_result(data, timeDiff):
	stamp = time.asctime(time.localtime(time.time()))
	payload = '{}: ch0: {}, ch1: {} [{}s]'.format(stamp, data.ch0, data.ch1, timeDiff)
	client.publish("light/data/", payload)

def count_tick(ticks):
	if ticks % 1000 == 0:
		client.publish("light/metrics/ticks/", ticks, 0, True)

def read_data(channel):
	try:
		return bus.read_i2c_block_data(TSLaddr, channel | TSLcmd, 2)
	except OSError as err:
		logging.error("Could not read data from bus")
		return None

def lightcheck():
	#Read Ch0 Word
	data0 = read_data(chan0)
	#Read CH1 Word
	data1 = read_data(chan1)
		
	if (data0 == None or data1 == None):
		return None

	# Convert the data to Integer
	ch0 = data0[1] * 256 + data0[0]
	ch1 = data1[1] * 256 + data1[0]
	
	vResults = ch0-ch1 #get visable light results
	if ch0 >= 50 and ch1 >= 5: #check against reading threshold 
		return Data(ch0, ch1)
	return None
if __name__ == "__main__":
	writebyte(TSLaddr, 0x00 | TSLcmd, TSLon) #Power On
	#Gain x1 at 402ms is the default so this line not required 
	#but change for different sensitivity
	writebyte(TSLaddr, 0x01 | TSLcmd,HighMed) #Gain x1 402ms
	time.sleep(1) #give time sensor to settle
	
	logging.info("sensor activated")
	
	previousTimestamp = time.time()
	counter = 0

	while 1:
		data = lightcheck()
		if data is not None:
			counter += 1
			count_tick(counter)
			timeDiff = round(time.time() - previousTimestamp, 1)
			previousTimestamp = time.time()
			publish_result(data, timeDiff)
			time.sleep(0.5)
	writebyte(TSLaddr, 0x00 | TSLcmd, TSLoff) #Power Off
