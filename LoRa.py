import time
import math
import utime
from ucollections import namedtuple
from urandom import getrandbits
from machine import SPI
from machine import Pin

#Constants
FLAGS_ACK = 0x80
FLAGS_REPT_SEND = 0x81
FLAGS_REPT_REPLY = 0x82

BROADCAST_ADDRESS = 255

REG_00_FIFO = 0x00
REG_01_OP_MODE = 0x01
REG_06_FRF_MSB = 0x06
REG_07_FRF_MID = 0x07
REG_08_FRF_LSB = 0x08
REG_0E_FIFO_TX_BASE_ADDR = 0x0e
REG_0F_FIFO_RX_BASE_ADDR = 0x0f
REG_10_FIFO_RX_CURRENT_ADDR = 0x10
REG_12_IRQ_FLAGS = 0x12
REG_13_RX_NB_BYTES = 0x13
REG_1D_MODEM_CONFIG1 = 0x1d
REG_1E_MODEM_CONFIG2 = 0x1e
REG_19_PKT_SNR_VALUE = 0x19
REG_1A_PKT_RSSI_VALUE = 0x1a
REG_20_PREAMBLE_MSB = 0x20
REG_21_PREAMBLE_LSB = 0x21
REG_22_PAYLOAD_LENGTH = 0x22
REG_26_MODEM_CONFIG3 = 0x26

REG_4D_PA_DAC = 0x4d
REG_40_DIO_MAPPING1 = 0x40
REG_0D_FIFO_ADDR_PTR = 0x0d

PA_DAC_ENABLE = 0x07
PA_DAC_DISABLE = 0x04
PA_SELECT = 0x80

CAD_DETECTED_MASK = 0x01
RX_DONE = 0x40
TX_DONE = 0x08
CAD_DONE = 0x04
CAD_DETECTED = 0x01

LONG_RANGE_MODE = 0x80
MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_TX = 0x03
MODE_RXCONTINUOUS = 0x05
MODE_CAD = 0x07

REG_09_PA_CONFIG = 0x09
FXOSC = 32000000.0
FSTEP = (FXOSC / 524288)

class ModemConfig():
    Bw125Cr45Sf128 = (0x72, 0x74, 0x04) #< Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on. Default medium range
    Bw500Cr45Sf128 = (0x92, 0x74, 0x04) #< Bw = 500 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on. Fast+short range
    Bw31_25Cr48Sf512 = (0x48, 0x94, 0x04) #< Bw = 31.25 kHz, Cr = 4/8, Sf = 512chips/symbol, CRC on. Slow+long range
    Bw125Cr48Sf4096 = (0x78, 0xc4, 0x0c) #/< Bw = 125 kHz, Cr = 4/8, Sf = 4096chips/symbol, low data rate, CRC on. Slow+long range
    Bw125Cr45Sf2048 = (0x72, 0xb4, 0x04) #< Bw = 125 kHz, Cr = 4/5, Sf = 2048chips/symbol, CRC on. Slow+long range

class SPIConfig():
    # spi pin defs for various boards (channel, sck, mosi, miso)
    rp2_0 = (0, 6, 7, 4)
    rp2_1 = (1, 10, 11, 8)
    esp8286_1 = (1, 14, 13, 12)
    esp32_1 = (1, 14, 13, 12)
    esp32_2 = (2, 18, 23, 19)

class LoRa(object):
    def __init__(self, spi_channel, interrupt, this_address, cs_pin, pico_logger, reset_pin=None, freq=433.3, tx_power=14,
                 modem_config=ModemConfig.Bw125Cr45Sf128, receive_all=False, acks=False, crypto=None):
        """
        Lora(channel, interrupt, this_address, cs_pin, reset_pin=None, freq=868.0, tx_power=14,
                 modem_config=ModemConfig.Bw125Cr45Sf128, receive_all=False, acks=False, crypto=None)
        channel: SPI channel, check SPIConfig for preconfigured names
        interrupt: GPIO interrupt pin
        this_address: set address for this device [0-254]
        cs_pin: chip select pin from microcontroller 
        reset_pin: the GPIO used to reset the RFM9x if connected
        freq: frequency in MHz
        tx_power: transmit power in dBm
        modem_config: Check ModemConfig. Default is compatible with the Radiohead library
        receive_all: if True, don't filter packets on address
        acks: if True, request acknowledgments
        crypto: if desired, an instance of ucrypto AES (https://docs.pycom.io/firmwareapi/micropython/ucrypto/) - not tested
        """
        
        self._spi_channel = spi_channel
        self._interrupt = interrupt
        self._cs_pin = cs_pin

        self._mode = None
        self._cad = None
        self._freq = freq
        self._tx_power = tx_power
        self._modem_config = modem_config
        self._receive_all = receive_all
        self._acks = acks

        self._this_address = this_address
        self._last_header_id = 0

        self._last_payload = None
        self._last_relay_payload = None
        self.crypto = crypto

        self.cad_timeout = 0
        self.send_retries = 2
        self.wait_packet_sent_timeout = 0.2
        self.retry_timeout = 0.3

        self.pico_logger = pico_logger
        self.relay_payload = None
        #Setup the module
        #gpio_interrupt = Pin(self._interrupt, Pin.IN, Pin.PULL_DOWN)
        gpio_interrupt = Pin(self._interrupt, Pin.IN)
        gpio_interrupt.irq(trigger=Pin.IRQ_RISING, handler=self._handle_interrupt)
        
        # reset the board
        if reset_pin:
            gpio_reset = Pin(reset_pin, Pin.OUT)
            gpio_reset.value(0)
            time.sleep(0.01)
            gpio_reset.value(1)
            time.sleep(0.01)

        # baud rate to 5MHz
        self.spi = SPI(self._spi_channel[0], 5000000,
                       sck=Pin(self._spi_channel[1]), mosi=Pin(self._spi_channel[2]), miso=Pin(self._spi_channel[3]))

        # cs gpio pin
        self.cs = Pin(self._cs_pin, Pin.OUT)
        self.cs.value(1)
        
        # set mode
        self._spi_write(REG_01_OP_MODE, MODE_SLEEP | LONG_RANGE_MODE)
        time.sleep(0.1)
        
        # check if mode is set
        assert self._spi_read(REG_01_OP_MODE) == (MODE_SLEEP | LONG_RANGE_MODE), \
            "LoRa initialization failed"

        print("LoRa Set!")
        self.pico_logger.WriteNewLog("LoRa Set!")
        self._spi_write(REG_0E_FIFO_TX_BASE_ADDR, 0)
        self._spi_write(REG_0F_FIFO_RX_BASE_ADDR, 0)
        
        self.set_mode_idle()

        # set modem config (Bw125Cr45Sf128)
        self._spi_write(REG_1D_MODEM_CONFIG1, self._modem_config[0])
        self._spi_write(REG_1E_MODEM_CONFIG2, self._modem_config[1])
        self._spi_write(REG_26_MODEM_CONFIG3, self._modem_config[2])

        # set preamble length (8)
        self._spi_write(REG_20_PREAMBLE_MSB, 0)
        self._spi_write(REG_21_PREAMBLE_LSB, 8)

        # set frequency
        frf = int((self._freq * 1000000.0) / FSTEP)
        self._spi_write(REG_06_FRF_MSB, (frf >> 16) & 0xff)
        self._spi_write(REG_07_FRF_MID, (frf >> 8) & 0xff)
        self._spi_write(REG_08_FRF_LSB, frf & 0xff)
        
        # Set tx power
        if self._tx_power < 5:
            self._tx_power = 5
        if self._tx_power > 23:
            self._tx_power = 23

        if self._tx_power < 20:
            self._spi_write(REG_4D_PA_DAC, PA_DAC_ENABLE)
            self._tx_power -= 3
        else:
            self._spi_write(REG_4D_PA_DAC, PA_DAC_DISABLE)

        self._spi_write(REG_09_PA_CONFIG, PA_SELECT | (self._tx_power - 5))
        
    def on_recv(self, message):
        # This should be overridden by the user
        pass

    def sleep(self):
        if self._mode != MODE_SLEEP:
            self._spi_write(REG_01_OP_MODE, MODE_SLEEP)
            self._mode = MODE_SLEEP

    def set_mode_tx(self):
        if self._mode != MODE_TX:
            self._spi_write(REG_01_OP_MODE, MODE_TX)
            self._spi_write(REG_40_DIO_MAPPING1, 0x40)  # Interrupt on TxDone
            self._mode = MODE_TX

    def set_mode_rx(self):
        if self._mode != MODE_RXCONTINUOUS:
            self._spi_write(REG_01_OP_MODE, MODE_RXCONTINUOUS)
            self._spi_write(REG_40_DIO_MAPPING1, 0x00)  # Interrupt on RxDone
            self._mode = MODE_RXCONTINUOUS
            
    def set_mode_cad(self):
        if self._mode != MODE_CAD:
            self._spi_write(REG_01_OP_MODE, MODE_CAD)
            self._spi_write(REG_40_DIO_MAPPING1, 0x80)  # Interrupt on CadDone
            self._mode = MODE_CAD

    def _is_channel_active(self):
        self.set_mode_cad()

        while self._mode == MODE_CAD:
            yield

        return self._cad
    
    def wait_cad(self):
        if not self.cad_timeout:
            return True

        start = time.time()
        for status in self._is_channel_active():
            if time.time() - start < self.cad_timeout:
                return False

            if status is None:
                time.sleep(0.1)
                continue
            else:
                return status

    def wait_packet_sent(self):
        # wait for `_handle_interrupt` to switch the mode back
        start = time.time()
        while time.time() - start < self.wait_packet_sent_timeout:
            if self._mode != MODE_TX:
                return True

        return False

    def set_mode_idle(self):
        if self._mode != MODE_STDBY:
            self._spi_write(REG_01_OP_MODE, MODE_STDBY)
            self._mode = MODE_STDBY

    def send(self, data, header_to, header_id=0, header_flags=0, relay_Addresses = None):
        utime.sleep(0.1)
        #Just so we dont send messages while its transmitting
        self.wait_packet_sent()
        self.set_mode_idle()
        self.wait_cad()

        header = [header_to, self._this_address, header_id, header_flags]
        self.relay_list_to_number(relay_Addresses, header)
        if type(data) == int:
            data = [data]
        elif type(data) == bytes:
            data = [p for p in data]
        elif type(data) == str:
            data = [ord(s) for s in data]

        if self.crypto:
            data = [b for b in self._encrypt(bytes(data))]
        
        payload = header + data
        self._spi_write(REG_0D_FIFO_ADDR_PTR, 0)
        self._spi_write(REG_00_FIFO, payload)
        self._spi_write(REG_22_PAYLOAD_LENGTH, len(payload))
        
        self.set_mode_tx()
        return True

    def send_to_wait(self, data, header_to, header_flags=0, retries=3, headerId = 0):
        if(headerId != 0):
            self._last_header_id = headerId
        else:
            self._last_header_id = self.get_new_header_id()

        for _ in range(retries + 1):
            self.send(data, header_to, header_id=self._last_header_id, header_flags=header_flags)
            self.set_mode_rx()

            if header_to == BROADCAST_ADDRESS:  # Don't wait for acks from a broadcast message
                return True

            start = time.time()
            while time.time() - start < self.retry_timeout + (self.retry_timeout * (getrandbits(16) / (2**16 - 1))):
                if self._last_payload:
                    if self._last_payload.header_to == self._this_address and \
                            self._last_payload.header_flags == FLAGS_ACK and \
                            self._last_payload.header_id == self._last_header_id:
                        self.pico_logger.WriteNewLog("Direct Message Reply: " + str(self._last_payload))
                        return self._last_payload
        self.pico_logger.WriteNewLog("1." + str(header_to) +".LoRa Could not Contact")
        return "1." + str(header_to) +".LoRa Could not Contact"

    def send_to_wait_relay(self, data, header_to, relay_Addresses, header_flags=FLAGS_REPT_SEND, retries=3, header_id = 0):
        if(header_id != 0):
            self._last_header_id = header_id
        else:
            self._last_header_id = self.get_new_header_id()

        for _ in range(retries + 1):
            
            self.send(data, header_to, header_id=self._last_header_id, header_flags=header_flags, relay_Addresses=relay_Addresses)

            self.set_mode_rx()
            self.wait_packet_sent()
            start = time.time()
            
            while time.time() - start < self.retry_timeout + (self.retry_timeout * (getrandbits(16) / (2**16 - 1))):
                if self._last_relay_payload or self._last_payload:

                    if (self._last_relay_payload and self._last_relay_payload.header_from_previous == self._this_address and \
                            self._last_relay_payload.header_from == header_to and \
                            self._last_relay_payload.header_flags == FLAGS_REPT_SEND and \
                            self._last_relay_payload.header_id == self._last_header_id) or\
                            (self._last_payload and self._last_payload.header_to == self._this_address and \
                            self._last_payload.header_flags == FLAGS_REPT_REPLY and \
                            self._last_payload.header_id == self._last_header_id):
                    
                        #TODO _last_header_id might be changed, we we try fix this? 
                        self.pico_logger.WriteNewLog("ACK: " + str(self._last_relay_payload))
                        
                        self._last_relay_payload = None
                        return True
        self.pico_logger.WriteNewLog("ACK: Failed")
        return False

    def get_new_header_id(self):
        if(self._last_header_id is None or self._last_header_id + 1 > 256):
            return 1
        return self._last_header_id + 1
        
    def send_ack(self, header_to, header_id):
        self.send(b'!', header_to, header_id, FLAGS_ACK)
        self.wait_packet_sent()

    def send_relay_ack(self, header_to, header_id):
        self.send(b'!', header_to, header_id, FLAGS_REPT_REPLY)
        self.wait_packet_sent()

    def _spi_write(self, register, payload):
        if type(payload) == int:
            payload = [payload]
        elif type(payload) == bytes:
            payload = [p for p in payload]
        elif type(payload) == str:
            payload = [ord(s) for s in payload]
        self.cs.value(0)
        self.spi.write(bytearray([register | 0x80] + payload))
        self.cs.value(1)

    def _spi_read(self, register, length=1):
        self.cs.value(0)
        if length == 1:
            data = self.spi.read(length + 1, register)[1]
        else:
            data = self.spi.read(length + 1, register)[1:]
        self.cs.value(1)
        return data
        
    def _decrypt(self, message):
        decrypted_msg = self.crypto.decrypt(message)
        msg_length = decrypted_msg[0]
        return decrypted_msg[1:msg_length + 1]

    def _encrypt(self, message):
        msg_length = len(message)
        padding = bytes(((math.ceil((msg_length + 1) / 16) * 16) - (msg_length + 1)) * [0])
        msg_bytes = bytes([msg_length]) + message + padding
        encrypted_msg = self.crypto.encrypt(msg_bytes)
        return encrypted_msg

    def _handle_interrupt(self, channel):
        irq_flags = self._spi_read(REG_12_IRQ_FLAGS)
        if self._mode == MODE_RXCONTINUOUS and (irq_flags & RX_DONE):
            
            packet_len = self._spi_read(REG_13_RX_NB_BYTES)
            self._spi_write(REG_0D_FIFO_ADDR_PTR, self._spi_read(REG_10_FIFO_RX_CURRENT_ADDR))

            packet = self._spi_read(REG_00_FIFO, packet_len)
            self._spi_write(REG_12_IRQ_FLAGS, 0xff)  # Clear all IRQ flags

            snr = self._spi_read(REG_19_PKT_SNR_VALUE) / 4
            rssi = self._spi_read(REG_1A_PKT_RSSI_VALUE)

            if snr < 0:
                rssi = snr + rssi
            else:
                rssi = rssi * 16 / 15

            if self._freq >= 779:
                rssi = round(rssi - 157, 2)
            else:
                rssi = round(rssi - 164, 2)

            if packet_len >= 5:
                header_to = packet[0]
                header_from = packet[1]
                header_id = packet[2]
                header_flags = packet[3]
                relay_Addresses_len = packet[4]
                
                relay_Addresses = []
                for charicter in packet[5: 5 + relay_Addresses_len]:
                    relay_Addresses.append(int(charicter))

                message = bytes(packet[5 + relay_Addresses_len:]) if packet_len > 5 else b''
                
                self.pico_logger.WriteNewLog("LoRa Message on Air: header_from: " + str(header_from) + "\theader_to: " + str(header_to) +  "\tmessage: " + str(message))
            
                if(self.relay_check_ack(header_to, header_from, header_id, header_flags, relay_Addresses_len, relay_Addresses, message, rssi, snr)):
                    return
                if self.crypto and len(message) % 16 == 0:
                    message = self._decrypt(message)

                if self._acks and header_to == self._this_address and not header_flags and FLAGS_ACK and relay_Addresses_len == 0:
                    self.send_ack(header_from, header_id)

                if(relay_Addresses_len > 0 and header_to == self._this_address and (header_flags ==  FLAGS_REPT_SEND or header_flags ==  FLAGS_REPT_REPLY) and FLAGS_ACK):
                    self.relay_payload = namedtuple(
                            "Payload",
                            ['message', 'header_to', 'header_from', 'header_from_previous', 'header_id', 'header_flags', 'relay_Addresses', 'rssi', 'snr']
                        )(message, header_to, header_from, self._this_address, header_id, header_flags, relay_Addresses, rssi, snr)
                    
                self.set_mode_rx()

                self._last_payload = namedtuple(
                    "Payload",
                    ['message', 'header_to', 'header_from', 'header_id', 'header_flags', 'relay_Addresses', 'rssi', 'snr']
                )(message, header_to, header_from, header_id, header_flags, relay_Addresses, rssi, snr)
                
                if not header_flags & FLAGS_ACK:
                    self.on_recv(self._last_payload)


        elif self._mode == MODE_TX and (irq_flags and TX_DONE):
            self.set_mode_idle()

        elif self._mode == MODE_CAD and (irq_flags and CAD_DONE):
            self._cad = irq_flags and CAD_DETECTED
            self.set_mode_idle()

        self._spi_write(REG_12_IRQ_FLAGS, 0xff)
            
    def relay_list_to_number(self, relay_Addresses, header):
        if(relay_Addresses is None):
            header.append(0)
            return
        header.append(len(relay_Addresses))

        for address in relay_Addresses:
            header.append(address)
                
    def relay_check_ack(self, header_to, header_from, header_id, header_flags, relay_Addresses_len, relay_Addresses, message, rssi, snr):
        #TODO make this more robust
        if(header_to != BROADCAST_ADDRESS or self._receive_all is False):
            if(self._this_address != header_to):
                if(relay_Addresses_len > 0 and self._this_address in relay_Addresses):
                    destination_position = relay_Addresses.index(header_from)
                    if(destination_position != 0 and relay_Addresses.index(self._this_address) + 1 == destination_position):
                        self._last_relay_payload = namedtuple(
                                "Payload",
                                ['message', 'header_to', 'header_from', 'header_from_previous', 'header_id', 'header_flags', 'rssi', 'snr']
                            )(message, header_to, header_from, self._this_address, header_id, header_flags, rssi, snr)
                return True
        return False

    #TODO Add Failure Reply
    def relay_check_repeat(self):
        if(self.relay_payload is None):
            return
        payload = self.relay_payload

        position = payload.relay_Addresses.index(self._this_address)
        
        if(position < len(payload.relay_Addresses) -1 ):
            self.pico_logger.WriteNewLog("Relaying Message to: " + str(payload.relay_Addresses[position + 1]) + "\t Message: " + str(payload.message) + "\tRelay List: " + str(payload.relay_Addresses))
            result = self.send_to_wait_relay(payload.message, payload.relay_Addresses[position + 1], header_flags=payload.header_flags, relay_Addresses=payload.relay_Addresses, header_id=payload.header_id)
            if(result):
                start = time.time_ns()
                responded_payload = self.repeat_wait_return(payload)
                if(responded_payload):
                    responded_position = responded_payload.relay_Addresses.index(self._this_address)
                    self._last_payload = None
                    result = self.send_to_wait_relay(responded_payload.message, responded_payload.relay_Addresses[responded_position + 1], header_flags=responded_payload.header_flags, relay_Addresses=responded_payload.relay_Addresses, header_id=responded_payload.header_id)
                    
                    self.pico_logger.WriteNewLog("LoRa got a response from Repeat Reply: " + str(responded_payload.message))
                else:    
                    self.pico_logger.WriteNewLog("2."+ str(payload.relay_Addresses[position + 1]) + ".Fording message never returned Time_ns: " + str(time.time_ns() - start))
            else:
                self.pico_logger.WriteNewLog("1." + str(payload.relay_Addresses[position + 1]) +".LoRa Could not Contact")
                #If failed, send message back
            self.relay_payload = None
            
        
        #Repeat Logic?
        elif(position == len(payload.relay_Addresses) -1):
            
            reply = self.on_recv(payload)
            relay_Addresses_reversed = self.reverse_list(payload.relay_Addresses)
            
            #Do not retry to send message as the other LoRa will request message again on its retry
            result = self.send_to_wait_relay(reply, relay_Addresses_reversed[1], header_flags=FLAGS_REPT_REPLY, relay_Addresses=relay_Addresses_reversed, header_id=payload.header_id, retries=0)
            self.relay_payload = None

    def repeat_wait_return(self, recieved_payload):
            position = recieved_payload.relay_Addresses.index(self._this_address)
            wait_repeater_jumps = len(recieved_payload.relay_Addresses) - position
            start = time.time()
            
            while time.time() - start < (self.retry_timeout + (self.retry_timeout * (getrandbits(16) / (2**16 - 1))))*4*wait_repeater_jumps:
                if self._last_payload and self._last_payload.header_flags == FLAGS_REPT_REPLY and \
                    self._last_payload.header_id == recieved_payload.header_id:
                    return self._last_payload
            return None        
        


    def relay_send(self, message, Send_To_ADDRESS, Send_To_Relay_Addresses, header_id = 0):
        result = self.send_to_wait_relay(str(message), Send_To_ADDRESS, Send_To_Relay_Addresses, header_id=header_id)
        if(result == False):
            self.pico_logger.WriteNewLog("1." + str(Send_To_ADDRESS) +".LoRa Could not Contact")
            return "1." + str(Send_To_ADDRESS) +".LoRa Could not Contact"
        
        payload = namedtuple(
                "Payload",
                ['message', 'header_id', 'relay_Addresses']
            )(message, self._last_header_id, Send_To_Relay_Addresses)
                    
        start = time.time_ns()
        responded_payload = self.repeat_wait_return(payload)

        if(responded_payload):
            self.pico_logger.WriteNewLog("Responded Relay: Time_ns: " + str(time.time_ns() - start) + "\t Paylaod: " + str(responded_payload))
            result = self.send_relay_ack(responded_payload.header_from, responded_payload.header_id)
            self.relay_payload = None
            return responded_payload
        else:
            self.relay_payload = None
            self.pico_logger.WriteNewLog("2."+ str(Send_To_ADDRESS) + ".Fording message never returned Time_ns: " + str(time.time_ns() - start))
            return "2."+ str(Send_To_ADDRESS) + ".Fording message never returned"
            
        
    def reverse_list(self, list):
        newList = []
        for element in reversed(list):
            newList.append(element)
        return newList
        

    def close(self):
        self.spi.deinit()



