import LoRa
import PicoLogger
from machine import Pin
from time import sleep
from sys import stdin
import utime
import uselect
import time
import machine
import ubinascii

debug_timer = 20

led = Pin(25, Pin.OUT)

led.toggle()
sleep(1)
led.toggle()

picoLogger = PicoLogger.PicoLogger()
# This is our callback function that runs when a message is received
def on_recv(payload):
    led.toggle()
    picoLogger.WriteNewLog("LoRa Recieved: " + str(payload))
    print("Getting Reply From Irrigation...Done")
    #utime.sleep(0.5)
    return "Pressure"

# Lora Parameters
RFM95_RST = 27
RFM95_SPIBUS = LoRa.SPIConfig.rp2_0
RFM95_CS = 5
RFM95_INT = 28
RF95_FREQ = 433.3
RF95_POW = 20

#Used For Testing Picos
CLIENT_ADDRESS1 = 1
CLIENT_ADDRESS2 = 2
CLIENT_ADDRESS3 = 3

Send_To_ADDRESS = 2
Send_To_Relay_Addresses = [1, 2, 3] #We need to add our Client Id so the message knows what LoRa to relay back to
#_thread.start_new_thread(serial.main, ())
# initialise radio                        #Is this Us?, Yes
CLIENT_ADDRESS = 0

if(str(ubinascii.hexlify(machine.unique_id()).decode()) == "e6612483cb821e21"):
    CLIENT_ADDRESS = 3
elif(str(ubinascii.hexlify(machine.unique_id()).decode()) == "e6612483cb487b29"):
    CLIENT_ADDRESS = 2
elif(str(ubinascii.hexlify(machine.unique_id()).decode()) == "e6612483cb7ab92b"):
    CLIENT_ADDRESS = 1

lora = LoRa.LoRa(RFM95_SPIBUS, RFM95_INT, CLIENT_ADDRESS, RFM95_CS, picoLogger, reset_pin=RFM95_RST, freq=RF95_FREQ, tx_power=RF95_POW, acks=True)

# set callback
lora.on_recv = on_recv

# set to listen continuously
lora.set_mode_rx()
# loop and wait for data
print("My Key: " + str(lora._this_address))
class PicoSerial():
    def __init__(self):
        self.buffered_input = []

    def getSerialInput(self):
        try:
            select_result = uselect.select([stdin], [], [], 0)
            while select_result[0]:
                input_character = stdin.read(1)
                self.buffered_input.append(input_character)
                select_result = uselect.select([stdin], [], [], 0)
            if(len(self.buffered_input)>0):
                message = ""
                for charicter in self.buffered_input:
                    if(charicter == "\t" or charicter == "\n" or charicter == "" or charicter == " "):
                        continue
                    message += charicter
                self.buffered_input = []
                return message
        finally:
            return None

picoSerial = PicoSerial()

start = time.time()

while True:
    message = None
    if(str(lora._this_address) == "1"):
        if(time.time() - start <  debug_timer):
            utime.sleep(0.1)
            continue
        print("Sending Message from Serial")
        message = "Test Relay V3"
    else:
        message = picoSerial.getSerialInput()
    if(message):
        if(message == ""):
            continue
        if(message == "SendLoggedDataToSerial"):
            picoLogger.SendLoggedDataToSerial()
            continue
        
        led.toggle()
        print("About to send: " + str(message))
        #lora.send_to_wait(str(message), Send_To_ADDRESS)
        result = lora.send_to_wait_relay(str(message), Send_To_ADDRESS, Send_To_Relay_Addresses)
        print(str(result))
        if(result):
            relay_result = lora.relay_check_repeat(True)
        led.toggle()
        #Listen after send? Do we need this?
        lora.set_mode_rx()
        #utime.sleep(20)
    
    lora.relay_check_repeat()
    
    start = time.time()

