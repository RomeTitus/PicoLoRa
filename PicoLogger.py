import machine
import utime
import os
import _thread

class PicoLogger:
    def __init__(self):
        self.LogFileName = "log.txt"
        self.Max_File_Size = 600000
        self.TimeDelta = None #Needs to be set from serial
        _thread.start_new_thread(self.ThreadWriteLog, ())
        self._PendingLoggedData = list()

    def WriteFile(self, logText):
        dateTime = self.TimeNow()
        dateTimeFormatted = "%04d-%02d-%02d %02d:%02d:%02d"%(dateTime[0:3] + dateTime[3:6])
        logText = dateTimeFormatted + "\t" + logText
        if("\r\n" not in logText):
            logText += "\r\n"
        log = open(self.LogFileName,"a")
        log.write(logText)
        log.flush()
        log.close()
        
    def TimeNow(self):
        if(self.TimeDelta is not None):
            return utime.localtime(utime.time() + self.TimeDelta)
        else:
            return utime.localtime(utime.time())
        
    def CheckFileSize(self):
        try:
            f = open(self.LogFileName,"r")
            f.seek(0, 2)
            size = f.tell()
            f.close()
            return size
        except:
            return 0 


    def RemoveOneLine(self):
        tmpName = self.LogFileName + '.bak'
        with open(self.LogFileName, 'r') as readFrom, open(tmpName, 'w') as writeTo:
            readFrom.readline()
            for char in readFrom:
                writeTo.write(char)

        readFrom.close()
        writeTo.close()
        os.remove(self.LogFileName)
        os.rename(tmpName, self.LogFileName)
  
    def SetDateTime(self, dateTimeInput):
        syncTime = utime.mktime(list(map(int, tuple(dateTimeInput.split(' ')))))
        self.TimeDelta = syncTime - int(utime.time())

    def WriteNewLog(self, logText):
        self._PendingLoggedData.append(logText)
        print(str(self._PendingLoggedData))

    def ThreadWriteLog(self):
        while True:
            for logged in list(self._PendingLoggedData):
                print("Found Logged Data: " + str(logged))
                while(self.CheckFileSize() > self.Max_File_Size):
                    self.RemoveOneLine()
                self.WriteFile(logged)
                self._PendingLoggedData.remove(logged)


    def SendLoggedDataToSerial(self):
        f = open(self.LogFileName,"r")
        line = f.readline()
        lineNumber = 0
        while line:
             print(str(line))
             lineNumber += 1
             line = f.readline()
        print("Total: " + str(lineNumber))
        print("Size: " + str(f.tell()) + "\t Max: " + str(self.Max_File_Size))
        f.close()



#Code Examples
"""
print("Creating Object!")
picoLogger = PicoLogger()
print("Created Object!")

print("Creating new log with no Date: ")
picoLogger.WriteNewLog("This is a new Log")

print("Creating new log with Updated Date: ")
picoLogger.SetDateTime("2022 08 23 17 03 33 0 0")
picoLogger.WriteNewLog("This is a new Log With A date")

utime.sleep_ms(800)
picoLogger.SendLoggedDataToSerial()

_thread.start_new_thread(second_thread, ())
"""

if __name__ == "__main__":
    picoLogger = PicoLogger()
    utime.sleep_ms(800)
    picoLogger.SendLoggedDataToSerial()