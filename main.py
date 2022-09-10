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

led = Pin(25, Pin.OUT)
#1 - Failed to send to Target
#2 - Relay never made it back

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
# initialise radio
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

print("My Key: " + str(lora._this_address))

class PicoSerial():
    def __init__(self):
        self.buffered_input = []

    def getSerialInput(self):
        try:
            select_result = uselect.select([stdin], [], [], 0)
            if(select_result[0]):
                utime.sleep_ms(100)
            while select_result[0]:
                input_character = stdin.read(1)
                #print(str(input_character))
                self.buffered_input.append(input_character)
                select_result = uselect.select([stdin], [], [], 0)
            if(len(self.buffered_input)>0):
                message = ""
                #print(str(self.buffered_input))
                for charicter in self.buffered_input:
                    if(charicter == "\t" or charicter == "\n" or charicter == "" or charicter == " "):
                        continue
                    message += charicter
                self.buffered_input = []
                print(str(message))
                return message
        except:
            return None

picoSerial = PicoSerial()

start = time.time()

while True:
    try:
        message = None
        message = picoSerial.getSerialInput()
        if(message):
            if(message == ""):
                continue
            elif(message == "SendLoggedDataToSerial"):
                picoLogger.SendLoggedDataToSerial()
                continue
            elif('send.' in message):
                splitmessage = message.split('.')
                if(len(splitmessage) < 3):
                    print("Error required send.[path].[message]")
                led.toggle()
                #send.path.message
                header_id = lora.get_new_header_id()
                print("0." + str(header_id) + ".[" + str(message) + "]")
                result = None
                
                Send_To_Relay_Addresses = []
                for address in splitmessage[1:len(splitmessage) -1]:
                    Send_To_Relay_Addresses.append(int(address))

                if(len(Send_To_Relay_Addresses) > 1):
                    result = lora.relay_send(str(splitmessage[len(splitmessage)-1:]), Send_To_Relay_Addresses[1], Send_To_Relay_Addresses, header_id)
                else:
                    result = lora.send_to_wait(str(splitmessage[len(splitmessage)-1:]), Send_To_Relay_Addresses[0], headerId = header_id)
            
                print(result)
                led.toggle()
                lora.set_mode_rx()
            
        lora.relay_check_repeat()
        
        start = time.time()
    except Exception as e:
        print("Exception: " + str(e))

