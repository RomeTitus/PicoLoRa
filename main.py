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

reply_timeout = 0.5 #seconds

#Commands
#Send.path.message [use H for message to get all RSSI and SNR]
#Send.path.path.message
#Recieved.headerId.message

#SetLoRaDateTime.YYYY MM DD HH MM SS
#SendLoggedDataToSerial

#Warning numbers
#1 - Failed to send to Target
#2 - Relay never made it back
#3 - Relay recieved, failed to reach headerId
#4 - Messaged Made it but controller did not reply back
#5 - Logged Data Failed to save

led.toggle()
sleep(1)
led.toggle()

picoLogger = PicoLogger.PicoLogger()

# This is our callback function that runs when a message is received
def on_recv(payload):
    led.toggle()
    headerFrom = payload.header_from
    message = payload.message
    if('relay_Addresses' in str(payload) and len(payload.relay_Addresses) > 0):
        headerFrom = payload.relay_Addresses[0]
    
    if(type(message) is bytes):
        message = message.decode("utf-8") 

    picoLogger.WriteNewLog("Recieved." + str(headerFrom)  + '.' + str(payload.header_id) + "." + str(message) + '.rssi' + str(payload.rssi) + '.snr' + str(payload.snr))
    
    print("Recieved." + str(headerFrom)  + '.' + str(payload.header_id) + "." + str(message) + '.rssi' + str(payload.rssi) + '.snr' + str(payload.snr))
    
    #0.5 seconds to reply, is that too fast?
    Start_reply_time = time.ticks_us()
    while (float(time.ticks_diff(time.ticks_us(), Start_reply_time)) < reply_timeout * 1000000):
        picoSerial.ReadInput()
        for timestamp in list(picoSerial.loRaReplies):
            for headerId in picoSerial.loRaReplies[timestamp]:
                if(str(headerId) == str(payload.header_id)):
                    picoLogger.WriteNewLog("Returning Message: " + str(picoSerial.loRaReplies[timestamp][headerId]))
                    reply = picoSerial.loRaReplies[timestamp][headerId]
                    #TODO do we want to delete straigh away?
                    del  picoSerial.loRaReplies[timestamp]
                    return reply
    return "4"

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
#Things to save:
#CLIENT_ADDRESS -- will be automatic
#freq -- From User
#tx_power -- From User
#modem_config -- From User

lora = LoRa.LoRa(RFM95_SPIBUS, RFM95_INT, CLIENT_ADDRESS, RFM95_CS, picoLogger, reset_pin=RFM95_RST, freq=RF95_FREQ, tx_power=RF95_POW, acks=True)

# set callback
lora.on_recv = on_recv

# set to listen continuously
lora.set_mode_rx()

print("My Key: " + str(lora._this_address))

class PicoSerial():
    def __init__(self):
        self.buffered_input = []
        self.loRaReplies = {}
        self.loRaSenting = {}

    def GetSerialInput(self):
        try:
            select_result = uselect.select([stdin], [], [], 0)
            if(select_result[0]):
                utime.sleep_ms(100)
            while select_result[0]:
                input_character = stdin.read(1)
                self.buffered_input.append(input_character)
                select_result = uselect.select([stdin], [], [], 0)
            if(len(self.buffered_input)>0):
                message = ""
                for charicter in self.buffered_input:
                    if(charicter == "\t" or charicter == "\n" or charicter == ""):
                        continue
                    message += charicter
                self.buffered_input = []
                return message
        except:
            return None

    def ReadInput(self):
        message = None
        message = self.GetSerialInput()
        if(message and message != ""):
            if("Recieved." in message):
                splitmessage = message.split('.')
                self.loRaReplies[utime.time()] = {splitmessage[1]: splitmessage[2]}
            else:
                splitmessage = message.split('.')
                self.loRaSenting[utime.time()] = message
        
        #Clean Old Messages
        for key in list(self.loRaReplies):
            if(utime.time() - key > 10):
                del self.loRaReplies[key]
                
        for key in list(self.loRaSenting):
            if(utime.time() - key > 10):
                del self.loRaSenting[key]

picoSerial = PicoSerial()

while True:
    try:
        for timestapm in list(picoSerial.loRaSenting):
            message = picoSerial.loRaSenting[timestapm]
            del picoSerial.loRaSenting[timestapm]
            #YYYY MM DD HH MM SS
            if("SetLoRaDateTime" in message):
                print(picoLogger.SetDateTime(message.split('.')[1]))

            if(message == "SendLoggedDataToSerial"):
                picoLogger.SendLoggedDataToSerial()
                continue

            elif('Send.' in message):
                splitmessage = message.split('.')
                if(len(splitmessage) < 3):
                    print("Error required Send.path.message")
                led.toggle()
                #send.path.message
                header_id = lora.get_new_header_id()
                print("0." + str(header_id) + "." + str(message))
                result = None
                
                Send_To_Relay_Addresses = []
                for address in splitmessage[1:len(splitmessage) -1]:
                    Send_To_Relay_Addresses.append(int(address))

                if(len(Send_To_Relay_Addresses) > 1):
                    Send_To_Relay_Addresses.insert(0, lora._this_address)
                    result = lora.relay_send(str(splitmessage[len(splitmessage)-1]), Send_To_Relay_Addresses[1], Send_To_Relay_Addresses, header_id)
                else:
                    result = lora.send_to_wait(str(splitmessage[len(splitmessage)-1]), Send_To_Relay_Addresses[0], headerId = header_id)
                    
                print(result)
                led.toggle()
                lora.set_mode_rx()
            
        lora.relay_check_repeat()
        picoLogger.commit_log()
        picoSerial.ReadInput()
        

    except Exception as e:
        print("Exception: " + str(e))

    

