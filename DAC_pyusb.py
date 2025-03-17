'''
This file uses pyusb to do USB Bulk Transfer
'''
import usb.core
import usb.util
from usb.backend import libusb1

import wave
import numpy as np
import struct

import serial

# ser = serial.Serial("COM8")

#  explicitly set backend
backend = libusb1.get_backend(find_library=lambda x: "libusb-1.0.dll")



# ====================== Device Config ====================
# Since we use USB Serial, based on usb_desc.h, idVendor=0x16C0, idProduct=0x0483
dev = usb.core.find(idVendor=0x16C0, idProduct=0x0483)
# print(dev)
if dev is None:
    raise ValueError('Device not found')
print(dev)
# dev.reset()

# cfg = dev.get_active_configuration()
# print(f"Current configuration: {cfg.bConfigurationValue}")

dev.set_configuration()

cfg = dev.get_active_configuration()
intf = cfg[(1,0)]  # use the first interface for bulk endpoint

print(dev)

ep_out = None
ep_in = None

for ep in intf:

    if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
        if ep.bEndpointAddress == 0x03:  #
            ep_out = ep
        print("ep_out", ep.bEndpointAddress)

    # Check for Endpoint 4 (TX)
    elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
        if ep.bEndpointAddress == 0x84: 
            ep_in = ep

        print("ep_in", ep.bEndpointAddress)


'''
ENDPOINT 0x3: Bulk OUT ===============================
       bLength          :    0x7 (7 bytes)
       bDescriptorType  :    0x5 Endpoint
       bEndpointAddress :    0x3 OUT
       bmAttributes     :    0x2 Bulk
       wMaxPacketSize   :  0x200 (512 bytes)
       bInterval        :    0x0
      ENDPOINT 0x84: Bulk IN ===============================
       bLength          :    0x7 (7 bytes)
       bDescriptorType  :    0x5 Endpoint
       bEndpointAddress :   0x84 IN
       bmAttributes     :    0x2 Bulk
       wMaxPacketSize   :  0x200 (512 bytes)
       bInterval        :    0x0

'''


# ========================== Wav file read ===================
WAV_FILE = "200.0kHz_100000Hz_square.wav"


with wave.open(WAV_FILE, "rb") as wav:
    num_channels = wav.getnchannels()
    sample_width = wav.getsampwidth()
    frame_rate = wav.getframerate()
    num_frames = wav.getnframes() # get number of samples

    raw_data = wav.readframes(num_frames) # get all samples in bytes object, little-endian so low-byte then high-byte
    # len(raw_data) = 2* num_frames 

# convert it into big endian 
# samples_int = [int.from_bytes(raw_data[i:i+2], byteorder="little", signed=False) #change to int (? unnecessary), length = numvber of samples
        #    for i in range(0, len(raw_data), 2)]

# samples_byte = samples_int.to_bytes(2, byteorder="large", signed=False)


# =========== send sampling rate to control the start ==========
bytes_rate = frame_rate.to_bytes(4, byteorder='little')
dev.write(ep_out, bytes_rate)

# =========== recieve ACK to send samples ==============
PACKET_SIZE = 512
send_index = 0

# =========== pad bytes into multipe of 512 ===========
# padding_size = (512 - (len(raw_data) % 512)) % 512  # Ensure no extra padding if already aligned
# raw_data += b'\x00' * padding_size  # Pad with zeroes

# we add extra byte at the end of raw data to make sure the raw data is not multiple of 512
if len(raw_data) % 512 == 0:
    raw_data += b'\x00\x00'

raw_data_length = len(raw_data)

print(raw_data_length)

# chunk_num = 5
# In the original setting, we send five chunks (5*512 bytes) once we receive 'S' signal from MCU
# However, this is very fast so the code cannot recieve them quickly and let the coming bytes accumatle in the 
# REAL BUFFER (btw PC and MCU)


exit_while = False
while not exit_while:
    try:
        # Poll for data with a short timeout
        ReadInData = dev.read(ep_in, 512, timeout=10)
        # this function will return bytes not char

        # observation: 
        # when the size in dev.read set to be *1*, it read a lot of bytes (which shouldn't be like that) more than  "5" as expected
        # when the size in dev.read set to be *512*, it will read only once (if the coming data is continueously send('s'), it will read 5 's' )

        # I suspect: (1) the packet sending mechanism (actully send fewer bytes (not 512) per time, but in total 512 )
        #            (2) how dev.read works

        # The method can temporaily solve this issue, but we need make sure everytime PC can only see '1' S in the buffer

        print(chr(ReadInData[0]))

        if chr(ReadInData[0]) == 'S':
            # send 1 chunk everytime it receive an S
           
            if send_index < (len(raw_data) - PACKET_SIZE):
                chunk = raw_data[send_index:send_index+PACKET_SIZE]
                # ------- Code to do try and except for timeout case: ----- 
                # try:
                #     dev.write(ep_out, chunk)  # Add a write timeout
                #     send_index += PACKET_SIZE
                #     print(f"Sent chunk  at index {send_index}")  # Debugging log
                #     # break  # Exit retry loop if successful
                # except usb.core.USBTimeoutError:
                #     print("Write timeout on attempt {attempt+1}, retrying...")
    
                dev.write(ep_out, chunk)
                send_index += PACKET_SIZE
                print(send_index)

            else:
                chunk = raw_data[send_index:] # get the rest of the value 
                dev.write(ep_out, chunk)
                send_index += len(chunk) 
                print(send_index)
                print(raw_data_length)
                print('=================== EOF ====================')
                exit_while = True

                break

           
            

        
    except usb.core.USBTimeoutError:
        print("No data available.")

print("EOF")
