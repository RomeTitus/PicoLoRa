import machine
import utime
import os
import _thread
import time

class PicoLogger:
    def __init__(self):
        self.LogFileName = "log.txt"
        self.Max_File_Size = 300000
        self.TimeDelta = None #Needs to be set from serial
        self._PendingLoggedData = list()
        self.timer = machine.Timer()
        print("Starting Timer")
        #self.timer.init(freq=1, mode=machine.Timer.PERIODIC, callback=self.writeCacheToLog)
        print("Started Timer")
        
    def writeCacheToLog(self, _):
        try:
            splitList = []
            for logged in list(self._PendingLoggedData):
                if(len(splitList) > 50):
                    if(self.CheckFileSize() > self.Max_File_Size):
                        self.SaveLogToNewFileDeleteOld()
                        print("Created New File!")
                    self.BatchWriteFile(splitList)
                    splitList = []

                splitList.append(logged)
                self._PendingLoggedData.remove(logged)
            if(len(splitList)>0):
                self.BatchWriteFile(splitList)
        except:
            self.timer.deinit()
    
    def WriteFile(self, logText):
        try:
            dateTime = self.TimeNow()
            dateTimeFormatted = "%04d-%02d-%02d %02d:%02d:%02d"%(dateTime[0:3] + dateTime[3:6])
            logText = dateTimeFormatted + "\t" + logText
            if("\r\n" not in logText):
                logText += "\r\n"
            log = open(self.LogFileName,"a")
            log.write(logText)
            log.flush()
            log.close()
        except Exception as e:
            print("WriteFile Exception: " + str(e))

    def BatchWriteFile(self, loggTextList):
        try:
            logFile = open(self.LogFileName,"a") 
            for logText in loggTextList:
                logFile.write(logText)
            logFile.flush()
            logFile.close()
        except Exception as e:
            print("BatchWriteFile Exception: " + str(e))
            
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
  
    def SaveLogToNewFileDeleteOld(self):
        for fileName in os.listdir():
            if(self.LogFileName in fileName):
                if(fileName == self.LogFileName):
                    os.rename(fileName, self.LogFileName + "1")
                elif(fileName[len(fileName)-1] == "1"):
                    os.rename(fileName, self.LogFileName + "2")
                else:
                    os.remove(fileName)

    #YYYY MM DD HH MM SS 0 0
    def SetDateTime(self, dateTimeInput):
        dateTimeInput = dateTimeInput + ' 0 0'
        syncTime = utime.mktime(list(map(int, tuple(dateTimeInput.split(' ')))))
        self.TimeDelta = syncTime - int(utime.time())

    def WriteNewLog(self, logText):
        dateTime = self.TimeNow()
        dateTimeFormatted = "%04d-%02d-%02d %02d:%02d:%02d"%(dateTime[0:3] + dateTime[3:6])
        logText = dateTimeFormatted + "\t" + logText
        if("\r\n" not in logText):
            logText += "\r\n"
        self._PendingLoggedData.append(logText)

    def SendLogToSerial(self, logFile):
        line = logFile.readline()
        lineNumber = 0
        while line:
             print(str(line))
             lineNumber += 1
             line = logFile.readline()
        return lineNumber

    def SendLoggedDataToSerial(self):
        totalLines = 0
        totalSize = 0
        for fileName in os.listdir():
            if(self.LogFileName not in fileName):
                continue
            file = open(fileName, "r")
            totalSize += file.tell()
            totalLines += self.SendLogToSerial(file)
            file.close()
        print("Total: " + str(totalLines))
        

print(str(__name__))
#if __name__ == "__main__":
picoLogger = PicoLogger()
print("Logging to serial")
picoLogger.SendLoggedDataToSerial()
print("Starting Logged test")
index = 1        

StartWrite = time.ticks_us()
                        #YYYY MM DD HH MM SS
picoLogger.SetDateTime("2022 09 10 21 35 11")
while True:
    #utime.sleep(0.1)
    foundFiles = 0
    picoLogTime = time.time_ns()
    start = time.ticks_us()
    picoLogger.WriteNewLog(str(index) + " :This is a test Log, hopefully we logg everything....")
    if (index % 100 == 0):
        picoLogger.writeCacheToLog(None)
        end = time.ticks_us()
        print(str(float(time.ticks_diff(end, start) / 100000)))
        for fileName in os.listdir():
            if(picoLogger.LogFileName in fileName):
                foundFiles += 1
        if(foundFiles == 3):
            print("TotalTime: " + str(float(time.ticks_diff(end, StartWrite) / 100000)))
            break
        #print("Logged Time_ms: " + str(time.time_ns() - picoLogTime))
    #utime.sleep(0.1)
    index += 1
