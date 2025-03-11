'''
This code achieves the basic function to 
update sampling rate

'''

import serial
import wave
import numpy as np
import struct


# ==========  declare serial object ============
ser = serial.Serial("COM5")

# ========== read wave file ==============
WAV_FILE = "square_44kHz_long.wav"

# ser = serial.Serial(SERIAL_PORT, timeout=0.1)  # Timeout prevents blocking

# Read WAV file
with wave.open(WAV_FILE, "rb") as wav:
    num_channels = wav.getnchannels()
    sample_width = wav.getsampwidth()
    frame_rate = wav.getframerate()
    num_frames = wav.getnframes() # get number of samples

    raw_data = wav.readframes(num_frames) # get all samples in bytes object, little-endian so low-byte then high-byte
    # len(raw_data) = 2* num_frames 


samples = [int.from_bytes(raw_data[i:i+2], byteorder="little", signed=False) #change to int (? unnecessary), length = numvber of samples
           for i in range(0, len(raw_data), 2)]

print("samples", len(samples))
# padding samples in multiple of 64
padding_length = (128 - len(samples) % 128) % 128  # Calculate the required padding to make the length a multiple of 64

# Pad the samples list
# samples = samples + [0] * padding_length
samples = samples[0:1024] # send 1024 samples for now


# ========== send sampling rate ===========
# 1. clear all read buffer to avoid confusion
ser.flushInput()

# 2. send sampling rate
command = f"{frame_rate}\n"  # Convert to string and add newline
ser.write(command.encode())  # Send to Arduino
ser.flush()

print(f"Sent sampling rate: {frame_rate} Hz")

# 3. get ack from MCU
while(ser.in_waiting == 0):
    continue

ready_signal = ser.read(1) 

# ======== send samples ========
index = 0
if ready_signal == b'S':
    ready_signal = b'R'
while ready_signal == b'R':
    # print("ready to send samples")

    # ========================
    # need to control ADC part
    # ========================

    # Start sending samples
    # Send samples with handshaking
   
    if index < len(samples)-1:
        chunk = samples[index:index+64]  # Send in small chunks (64 samples per chunk)
        for sample in chunk:
            ser.write(sample.to_bytes(2, byteorder="little", signed=False))
        index += len(chunk) 

        while(ser.in_waiting == 0):
            continue

        ready_signal = ser.read(1) 
        # print("After sampling rate ACK, signal is ", ready_signal)

    else:
        print("Finish sending")
        ready_signal = b'Q' 
        break

print(ser.out_waiting) # no data in output buffer
print(index)
print(ser.read(1) )
print(ser.read(1) )
print(ser.read(1) )
print(ser.read(1) )
print(ser.read(1) )
print(ser.read(1) )
print(index)


    





