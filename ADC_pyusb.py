'''
This file uses pyusb to do USB Bulk Transfer for ADC only
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

print(dev.speed)

# Step 1: send sampling rate
frame_rate = 90000
bytes_rate = frame_rate.to_bytes(4, byteorder='little')
dev.write(ep_out, bytes_rate)

# Step 2: receive '1' ACK
getSR_ACK = dev.read(ep_in, 512, timeout=1000)
print(chr(getSR_ACK[0]))

# Step 3: start ADC timer 
# Since we have very large buffer, it takes some time to fill the first half of buffer.
# Consider this, our procedure should be:
# 1. send SR to DAC and send half of samples to MCU(DAC)
# 2. send SR to ADC and receive ACK from MCU(ADC), ADC starts working
# 3. send signal to DAC to start transmit

MAX_BUFFER_SIZE = 409600
HLAF_MAX_BUFFER_SIZE = MAX_BUFFER_SIZE//2


output_filename = "output.wav"
with wave.open(output_filename, 'wb') as output_file:
    output_file.setnchannels(1)  # Mono audio
    output_file.setsampwidth(2)  # 16-bit samples (2 bytes per sample)
    output_file.setframerate(frame_rate)

    i = 0
    recorded_samples = np.array([], dtype=np.int16)


    exit_while = False
    num = 0
    while num <= 10000:
        try:
            # Poll for data with a short timeout
            ReadInData = dev.read(ep_in, HLAF_MAX_BUFFER_SIZE, timeout=10)
            # print(ReadInData)
            np_data = np.frombuffer(ReadInData, dtype='>u2') # > large-endian, u2: unint16
            # num_samples = len(ReadInData) // 2  #ensure integer 
            # ReadInSample = struct.unpack('<' + 'h' * num_samples, ReadInData)
            # print(np_data)
            recorded_samples = np.concatenate((recorded_samples, np_data))

            num =len(recorded_samples)
            print(num)
            # print("YEAHHHHHH")
        except:
            print("no data avaiable")

    
    
    dev.write(ep_out, 'e') # send a signal to ADC so it will stop timer and reset itself
    
    output_file.writeframes(np.array(recorded_samples, dtype=np.int16).tobytes())
    print("ADC recording completed. Saved as output.wav.")

# clean all buffer
try:
    ReadInData = dev.read(ep_in, HLAF_MAX_BUFFER_SIZE, timeout=10)
except:
    print("no data in buffer")
print("EOF")

