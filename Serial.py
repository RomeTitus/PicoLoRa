import machine
from sys import stdin
import uselect
import utime

class PicoSerial():
    def __init__(self):
        self.buffered_input = []
        self.loRaReplies = {}
        self.loRaSending = {}
        self.uart = machine.UART(0, 38400)
        self.pinSerialWrite = machine.Pin(2, machine.Pin.OUT)
        self.pinSerialWrite.low()

    def GetSerialUSBInput(self):
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

    def GetSerialPinInput(self):
        try:
            message = ""
            bitesLen = self.uart.any()
            while bitesLen:
                uartCharicter = self.uart.read(bitesLen)
                utime.sleep(0.1)
                bitesLen = self.uart.any()
                if(uartCharicter is not None):
                    message += uartCharicter.decode("utf-8") 
            if(message == ""):
                return None
            
            return message
        except:
            return None

    def ReadInput(self):
        self._SetMessageToDic(self.GetSerialUSBInput())
        self._SetMessageToDic(self.GetSerialPinInput())
        
        #Clean Old Messages
        for key in list(self.loRaReplies):
            if(utime.time() - key > 10):
                del self.loRaReplies[key]
                
        for key in list(self.loRaSending):
            if(utime.time() - key > 10):
                del self.loRaSending[key]

    def _SetMessageToDic(self, message):
        if(message and message != ""):
            if("Recieved," in message):
                splitmessage = message.split(',')
                self.loRaReplies[utime.time()] = {splitmessage[1]: splitmessage[2]}
            else:
                self.loRaSending[utime.time()] = message

    def Write(self, message, streamDataComplete = True):
        if(message is not None):
            print(message)
            self.pinSerialWrite.high()
            self.uart.write(message)
        if(streamDataComplete):
            utime.sleep(0.5)
            self.pinSerialWrite.low()
            


