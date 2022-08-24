import LoRa
import PicoLogger
from machine import Pin
from time import sleep
import utime

led = Pin(25, Pin.OUT)

led.toggle()
sleep(1)
led.toggle()

picoLogger = PicoLogger.PicoLogger()

# This is our callback function that runs when a message is received
def on_recv(payload):
    led.toggle()
    picoLogger.WriteNewLog("LoRa Recieved: " + str(payload))
    print("From:", payload.header_from)
    print("Received:", payload.message)
    print("RSSI: {}; SNR: {}".format(payload.rssi, payload.snr))

# Lora Parameters
RFM95_RST = 27
RFM95_SPIBUS = LoRa.SPIConfig.rp2_0
RFM95_CS = 5
RFM95_INT = 28
RF95_FREQ = 433.3
RF95_POW = 20
CLIENT_ADDRESS = 1
SERVER_ADDRESS = 2

# initialise radio
lora = LoRa.LoRa(RFM95_SPIBUS, RFM95_INT, SERVER_ADDRESS, RFM95_CS, picoLogger, reset_pin=RFM95_RST, freq=RF95_FREQ, tx_power=RF95_POW, acks=True)

# set callback
lora.on_recv = on_recv

# set to listen continuously
lora.set_mode_rx()

# loop and wait for data
while True:
    message = input ("Enter Message to send: ")
    if(message == ""):
        continue
    if(message == "SendLoggedDataToSerial"):
        picoLogger.SendLoggedDataToSerial()
        continue
    
    led.toggle()
    lora.send_to_wait(str(message), SERVER_ADDRESS)
    led.toggle()
    #Listen after send? Do we need this?
    lora.set_mode_rx()
    

