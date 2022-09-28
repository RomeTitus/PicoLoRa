from ucollections import namedtuple
#Things to save:
#CLIENT_ADDRESS -- will be automatic?
#freq -- From User
#tx_power -- From User
#modem_config -- From User

class LoRaConfig:
    def __init__(self, picoSerial, picoLogger):
        self.PicoLogger = picoLogger
        self.PicoSerial = picoSerial
        self.ConfigFileName = "Config.csv"
    
    def write_config(self, config):
        configList = config.split(',')
        notification = self.validate_config(configList)
        if(len(notification) > 0):
            return notification
        try:
            logFile = open(self.ConfigFileName,"w") 
            logFile.write(config)
            logFile.flush()
            logFile.close()
            return self.read_config()
        except Exception as e:
            self.PicoSerial.Write("4: write_config Logged data could not be saved to board: " + str(e))
            self.PicoLogger.WriteNewLog("4: write_config Logged data could not be saved to board: " + str(e))

    def read_config(self):
        try:
            configFile = open(self.ConfigFileName, "r")
            line = str(configFile.readline())
            if(len(line) < 1 ):
                return None
            configList = line.split(",")

            return namedtuple(
                            "Config",
                            ['client_address', 'freq', 'tx_power', 'modem_config']
                            )(int(configList[0]), float(configList[1]), int(configList[2]), int(configList[3]))
        except Exception as e:
            self.PicoSerial.Write("LoRa Not Set Up")
            self.PicoLogger.WriteNewLog("LoRa Not Set Up")

    def validate_config(self, configList):
        try:
            notification = ""
            if(len(configList) < 4 or len(configList) > 4):
                return "Config Parameters too short/long, required 4 settings sepperated by ','"
        
            client_address = int(configList[0])
            freq = float(configList[1])
            tx_power = int(configList[2])
            modem_config = int(configList[3])

            if(client_address > 254 or client_address < 0):
                notification += "Invalid Modem Config\n"

            if(freq > 450 or freq < 420):
                notification += "Invalid frequency, support 420-450Mhz\n"

            if(tx_power > 23 or tx_power < 5):
                notification += "Invalid tx_power, support 5-23\n"

            if(modem_config > 4 or modem_config < 0):
                notification += "Invalid Modem Config, supports 0-4"
            return notification

        except Exception as e:
            return "Invalid Format: " + str(e)
