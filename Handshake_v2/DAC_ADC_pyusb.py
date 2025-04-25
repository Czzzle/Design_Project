import usb.core
import usb.util
from usb.backend import libusb1

import wave
import numpy as np
import struct

import serial
import time

# Threading library
from queue import Queue 
import threading 


# =============================================
# ========== Constant setting
# =============================================
# Buffer and packet
MAX_BUFFER_SIZE = 81920  #ADC buffer size
HLAF_MAX_BUFFER_SIZE = MAX_BUFFER_SIZE//2 # ADC half buffer size
PACKET_SIZE = 512 # the size for one-time send and receive, # of bytes 

# Threading parameters
DAC_finished = False  
ADC_ready = False
ADC_ready = threading.Event()
DAC_finished = threading.Event()

# --------------------------
# input and output file name (NEED UPDATE)
# --------------------------
# input_filename = "80.0kHz_8000.0Hz_30_sine.wav" 
input_filename = "180.0kHz_18000.0Hz_30_sine.wav" 
output_filename = "output.wav"


# =============================================
# ========= Get DAC, ADC device
# =============================================
def getDevices():
    #  explicitly set backend
    backend = libusb1.get_backend(find_library=lambda x: "libusb-1.0.dll")

    # ----- DAC device setup
    DAC_dev = usb.core.find(idVendor=0x16C0, idProduct=0x048B)
    if DAC_dev is None:
        raise ValueError('DAC_device not found')

    DAC_dev.set_configuration()
    DAC_cfg = DAC_dev.get_active_configuration()
    DAC_intf = DAC_cfg[(1,0)]  # use the first interface for bulk endpoint

    # print(DAC_dev)

    DAC_ep_out = None
    DAC_ep_in = None

    for ep in DAC_intf:

        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            if ep.bEndpointAddress == 0x03:  #
                DAC_ep_out = ep
            print("DAC_ep_out", ep.bEndpointAddress)

        # Check for Endpoint 4 (TX)
        elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
            if ep.bEndpointAddress == 0x83: 
                DAC_ep_in = ep

            print("DAC_ep_in", ep.bEndpointAddress)


    # ------- ADC device setup
    ADC_dev = usb.core.find(idVendor=0x16C0, idProduct=0x0483)
    if ADC_dev is None:
        raise ValueError('ADC_device not found')
    # print(ADC_dev)

    ADC_dev.set_configuration()
    ADC_cfg = ADC_dev.get_active_configuration()
    ADC_intf = ADC_cfg[(1,0)]  # use the first interface for bulk endpoint

    # print(ADC_dev)

    ADC_ep_out = None
    ADC_ep_in = None

    for ep in ADC_intf:

        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            if ep.bEndpointAddress == 0x03:  #
                ADC_ep_out = ep
            print("ADC_ep_out", ep.bEndpointAddress)

        # Check for Endpoint 4 (TX)
        elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
            if ep.bEndpointAddress == 0x84: 
                ADC_ep_in = ep

            print("ADC_ep_in", ep.bEndpointAddress)

    return [DAC_dev, DAC_ep_in, DAC_ep_out, ADC_dev, ADC_ep_in, ADC_ep_out]

# Usage:
# [DAC_dev, DAC_ep_in, DAC_ep_out, ADC_dev, ADC_ep_in, ADC_ep_out] = getDevices()



# =============================================
# ========= DAC Thread Function
# =============================================
def runDAC(DAC_dev, DAC_ep_in, DAC_ep_out):
    global ADC_ready, DAC_finished, input_filename

    # ----------------------------
    # ----- Process input file ---
    # ----------------------------
    with wave.open(input_filename, "rb") as wav:
        num_channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        frame_rate = wav.getframerate()
        num_frames = wav.getnframes() # get number of samples

        raw_data = wav.readframes(num_frames) # get all samples in bytes object, little-endian so low-byte then high-byte

    # make sure there are tiles
    if len(raw_data) % PACKET_SIZE == 0:
        raw_data += b'\x00\x00'
    raw_data_length = len(raw_data)

    print("[DAC] Total number of bytes: ",raw_data_length)

    # change the format of sampling rate
    bytes_rate = frame_rate.to_bytes(4, byteorder='little')


    # ----------------------------
    # --- wait for ADC to be ready
    # ----------------------------
    print("[DAC] Waiting for ADC to be ready...")
    ADC_ready.wait()
    print("[DAC] ADC is ready, start DAC now...")

    # ----------------------------
    # ---- Start working ---------
    # ----------------------------

    # 1. send sampling rate
    DAC_dev.write(DAC_ep_out, bytes_rate)

    # 2. send samples
    send_index = 0

    exit_while = False
    while not exit_while:
        try:
            # Poll for data with a short timeout
            ReadInData = DAC_dev.read(DAC_ep_in, 512, timeout=10)   # this function will return bytes not char
         
            # print('[DAC] send signal: ', chr(ReadInData[0]))

            if chr(ReadInData[0]) == 'S':
                # send 1 chunk/packet everytime it receive an S
            
                if send_index < (len(raw_data) - PACKET_SIZE):
                    chunk = raw_data[send_index:send_index+PACKET_SIZE]
                    DAC_dev.write(DAC_ep_out, chunk)
                    send_index += PACKET_SIZE
                    # print(send_index)

                else:
                    chunk = raw_data[send_index:] # get the rest of the value 
                    DAC_dev.write(DAC_ep_out, chunk)
                    send_index += len(chunk) 
                    print(send_index)
                    print(raw_data_length)
                    print('[DAC] ============ PC send all samples ===============')
                    exit_while = True

                    break

        except usb.core.USBTimeoutError:
            continue
            # print("[DAC] No 'S' send from DAC.")

    # 3. wait for DAC to read samples in buffer and send to ADC
    exit_while = False
    while not exit_while:
        try:
            ReadInData = DAC_dev.read(DAC_ep_in, 512, timeout=10)
            if chr(ReadInData[0]) == 'E':
                print('[DAC] send signal: ', chr(ReadInData[0]))
                print('[DAC] DAC timer ends')
                time.sleep(1) # sleep for 1 seconds s
                DAC_finished.set()
                exit_while = True
        except:
            print("[DAC] No 'E' send from DAC.")
    
    print("[DAC] finish and close")


# =============================================
# ========= ADC Thread Function
# =============================================
def runADC(ADC_dev, ADC_ep_in, ADC_ep_out):
    global ADC_ready, DAC_finished, input_filename, output_filename

    recorded_samples_list = []

    # 0: read all dummy data may exist in the input buffer
    try:
        ReadInData = ADC_dev.read(ADC_ep_in, HLAF_MAX_BUFFER_SIZE, timeout=10)
        ReadInData = ADC_dev.read(ADC_ep_in, HLAF_MAX_BUFFER_SIZE, timeout=10)
        print("[ADC] dummy data is in buffer")
    except:
        print("[ADC] no dummy data is in buffer")
    
    # 1. get input sampling rate and send SR to ADC
    with wave.open(input_filename, "rb") as wav:
        frame_rate = wav.getframerate()
    bytes_rate = frame_rate.to_bytes(4, byteorder='little')
    ADC_dev.write(ADC_ep_out, bytes_rate)

    # 2. receive ADC timer start signal '1'
    getSR_ACK = ADC_dev.read(ADC_ep_in, 512, timeout=1000)
    print("[ADC] ready")
    ADC_ready.set()

    # 3. read incoming signals
    with wave.open(output_filename, 'wb') as output_file:
        output_file.setnchannels(1)  # Mono audio
        output_file.setsampwidth(2)  # 16-bit samples (2 bytes per sample)
        output_file.setframerate(frame_rate)

        i = 0
        # recorded_samples = np.array([], dtype=np.int16)
        # recorded_samples = np.array([], dtype=np.uint16) # test to work on uint16 since ADC output is use 0 as base

        exit_while = False
        num = 0
        while not DAC_finished.is_set():
        # while num <900000:
            try:
                # Poll for data with a short timeout
                ReadInData = ADC_dev.read(ADC_ep_in, HLAF_MAX_BUFFER_SIZE, timeout=10)
                np_data = np.frombuffer(ReadInData, dtype='>i2') # > large-endian, u2: unint16, i2:signed int16
                recorded_samples_list.append(np_data)
                # recorded_samples = np.concatenate((recorded_samples, np_data))

                num +=len(np_data)
                # print(num)
            
            except:
                continue
        
        ADC_dev.write(ADC_ep_out, 'e') # send a signal to ADC so it will stop timer and reset itself
        recorded_samples = np.concatenate(recorded_samples_list)
        output_file.writeframes(np.array(recorded_samples, dtype=np.int16).tobytes()) 

    print("[ADC] byte num" ,num*2)
    print("[ADC] recording completed. Saved as output.wav.")

    # 4. clean all buffer
    while True:
        try:
            ReadInData = ADC_dev.read(ADC_ep_in, HLAF_MAX_BUFFER_SIZE, timeout=10)
            # ReadInData = ADC_dev.read(ADC_ep_in, HLAF_MAX_BUFFER_SIZE, timeout=10)
        except:
            print("no data in buffer")
            break
    print("EOF")


# =============================================
# ========= Main Function
# =============================================
def main():
    [DAC_dev, DAC_ep_in, DAC_ep_out, ADC_dev, ADC_ep_in, ADC_ep_out] = getDevices()
    # runDAC(DAC_dev, DAC_ep_in, DAC_ep_out)
    # runADC(ADC_dev, ADC_ep_in, ADC_ep_out)

    thread_adc = threading.Thread(target=runADC, args=(ADC_dev, ADC_ep_in, ADC_ep_out))
    thread_dac = threading.Thread(target=runDAC, args=(DAC_dev, DAC_ep_in, DAC_ep_out))

    thread_adc.start()
    thread_dac.start()

    thread_dac.join()
    thread_adc.join()

main()