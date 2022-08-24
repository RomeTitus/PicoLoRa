import machine
import utime
print()
print("                           YYYY MM DD HH MM SS")
dateTimeInput = (input ("Enter current date & time: "))+' 0 0'
syncTime = utime.mktime(list(map(int, tuple(dateTimeInput.split(' ')))))
timeDelta = syncTime - int(utime.time())


def timeNow():
    return utime.localtime(utime.time() + timeDelta)

while True:
    dateTime = timeNow()
    print(str(dateTime))
    print("%04d-%02d-%02d %02d:%02d:%02d"%(dateTime[0:3] + dateTime[3:6]))
    #print("{04d}".format(dateTime[2], dateTime[1], dateTime[0], dateTime[3]))
    utime.sleep(1)