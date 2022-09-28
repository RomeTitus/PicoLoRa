import utime
import os

class PicoLogger:
    def __init__(self, picoSerial):
        self.PicoSerial = picoSerial
        self.LogFileName = "log.txt"
        self.Max_File_Size = 300000
        self.TimeDelta = None #Needs to be set from serial
        self._PendingLoggedData = list()
        self.lastLogged = 0
        self.loggedTimeFrame = 60 #Save Log every 1 min
        
    def commit_log(self, forceCommit = False):
        if (utime.time() - self.lastLogged < self.loggedTimeFrame and forceCommit == False):
            return
        self.lastLogged = utime.time()    
        
        try:
            splitList = []
            for logged in list(self._PendingLoggedData):
                if(len(splitList) > 50):
                    if(self.CheckFileSize() > self.Max_File_Size):
                        self.SaveLogToNewFileDeleteOld()
                    self.BatchWriteFile(splitList)
                    splitList = []

                splitList.append(logged)
                self._PendingLoggedData.remove(logged)
            if(len(splitList)>0):
                self.BatchWriteFile(splitList)
        except Exception as e:
            self.PicoSerial.Write("4: commit_log Logged data could not be saved to board: " + str(e))

    def BatchWriteFile(self, loggTextList):
        try:
            logFile = open(self.LogFileName,"a") 
            for logText in loggTextList:
                logFile.write(logText)
            logFile.flush()
            logFile.close()
        except Exception as e:
            self.PicoSerial.Write("4: BatchWriteFile Logged data could not be saved to board: " + str(e))

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
  
    def SaveLogToNewFileDeleteOld(self):
        for fileName in os.listdir():
            if(self.LogFileName in fileName):
                if(fileName == self.LogFileName):
                    os.rename(fileName, self.LogFileName + "1")
                elif(fileName[len(fileName)-1] == "1"):
                    os.rename(fileName, self.LogFileName + "2")
                else:
                    os.remove(fileName)

    #YYYY MM DD HH MM SS
    def SetDateTime(self, dateTimeInput):
        dateTimeInput = dateTimeInput + ' 0 0'
        syncTime = utime.mktime(list(map(int, tuple(dateTimeInput.split(' ')))))
        self.TimeDelta = syncTime - int(utime.time())
        dateTime = self.TimeNow()
        return str("%04d-%02d-%02d %02d:%02d:%02d"%(dateTime[0:3] + dateTime[3:6]))

    def WriteNewLog(self, logText):
        dateTime = self.TimeNow()
        dateTimeFormatted = "%04d-%02d-%02d %02d:%02d:%02d"%(dateTime[0:3] + dateTime[3:6])
        logText = dateTimeFormatted + "\t" + logText
        if("\r\n" not in logText):
            logText += "\r\n"
        self._PendingLoggedData.append(logText)

    def SendLogToSerial(self, logFile):
        line = logFile.readline()
        while line:
             self.PicoSerial.Write(str(line), False)
             line = logFile.readline()
        
    def SendLoggedDataToSerial(self):
        self.commit_log(True)
        for fileName in os.listdir():
            if(self.LogFileName not in fileName):
                continue
            file = open(fileName, "r")
            self.SendLogToSerial(file)
            file.close()
        self.PicoSerial.Write(None)