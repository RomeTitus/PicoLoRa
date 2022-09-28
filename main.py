import utime
import LoRa
import PicoLogger
import LoRaConfig
import Serial
import machine
from time import sleep

import time

led = machine.Pin(25, machine.Pin.OUT)


picoSerial = Serial.PicoSerial()
picoLogger = PicoLogger.PicoLogger(picoSerial)
loRaConfig = LoRaConfig.LoRaConfig(picoSerial, picoLogger)
reply_timeout = 0.5 #seconds

#Commands
#Send,path,message [use H for message to get all RSSI and SNR]
#Send,path,path,message
#Recieved,headerId,message
#SetLoRaDateTime,YYYY MM DD HH MM SS
#SendLoggedDataToSerial
#Config,client_address,freq,tx_power,modem_config

#Warning numbers
#1 - Failed to send to Target
#2 - Relay never made it back
#3 - Relay recieved, failed to reach headerId
#4 - Messaged Made it but controller did not reply back
#5 - Logged Data Failed to save

led.toggle()
sleep(1)
led.toggle()



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
    
    picoSerial.Write("Recieved." + str(headerFrom)  + '.' + str(payload.header_id) + "." + str(message) + '.rssi' + str(payload.rssi) + '.snr' + str(payload.snr))
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





def send_to_lora(message):
    splitmessage = message.split(',')
    if(len(splitmessage) < 3):
        picoSerial.Write("Error required Send,path,message")
        return
    led.toggle()

    if(lora is None):
        picoSerial.Write("0,404," + str(message))
        return
    #send,path,message
    header_id = lora.get_new_header_id()
    picoSerial.Write("0," + str(header_id) + "," + str(message))
    result = None
    
    Send_To_Relay_Addresses = []
    for address in splitmessage[1:len(splitmessage) -1]:
        Send_To_Relay_Addresses.append(int(address))

    if(len(Send_To_Relay_Addresses) > 1):
        Send_To_Relay_Addresses.insert(0, lora._this_address)
        result = lora.relay_send(str(splitmessage[len(splitmessage)-1]), Send_To_Relay_Addresses[1], Send_To_Relay_Addresses, header_id)
    else:
        result = lora.send_to_wait(str(splitmessage[len(splitmessage)-1]), Send_To_Relay_Addresses[0], headerId = header_id)
    picoSerial.Write(str(result))
    led.toggle()
    lora.set_mode_rx()

def set_lora_config(message):
    config =  message[7:]
    result = loRaConfig.write_config(config)
    picoSerial.Write(str(result))
        
    if(type(result) == str):
        return
    return get_LoRa(result)

def get_LoRa(pico_logger):
    try:
        modemList = [LoRa.ModemConfig.Bw125Cr45Sf128, LoRa.ModemConfig.Bw500Cr45Sf128, LoRa.ModemConfig.Bw31_25Cr48Sf512, LoRa.ModemConfig.Bw125Cr48Sf4096, LoRa.ModemConfig.Bw125Cr45Sf2048]
        loraConfig = loRaConfig.read_config()
        if(loraConfig is None):
            pico_logger.WriteNewLog("LoRa not setup")
            return loraConfig
        lora = LoRa.LoRa(RFM95_SPIBUS, RFM95_INT, loraConfig.client_address, RFM95_CS, picoLogger, reset_pin=RFM95_RST, freq=loraConfig.freq, tx_power=loraConfig.tx_power, acks=True, modem_config=modemList[loraConfig.modem_config])
        # set callback
        lora.on_recv = on_recv
        # set to listen continuously
        lora.set_mode_rx()
        return lora
    except Exception as e:
        picoSerial.Write("LoRa Fatal: " + str(e))

lora = get_LoRa(picoLogger)

while True:
    try:
        for timestapm in list(picoSerial.loRaSenting):
            message = picoSerial.loRaSenting[timestapm]
            del picoSerial.loRaSenting[timestapm]
            print(message)
            
            #YYYY MM DD HH MM SS
            if("SetLoRaDateTime" in message):
                picoSerial.Write(picoLogger.SetDateTime(message.split(',')[1]))

            if(message == "SendLoggedDataToSerial"):
                picoLogger.SendLoggedDataToSerial()
                continue

            elif('Send,' in message):
                send_to_lora(message)
                
            elif('Config,' in message):
                lora = set_lora_config(message)
            
        if(lora is not None):
            lora.relay_check_repeat()
        
        picoLogger.commit_log()
        picoSerial.ReadInput()
        #picoSerial.Write("This is a Test")
        #utime.sleep(3)
        

    except Exception as e:
        picoSerial.Write("Exception: " + str(e))

    

