import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile as wav

Fs, Y = wav.read("output.wav")
Y = Y.astype(np.int16)
print(Y)
# Fs = 100000
Y = (Y / 65535.0)  *5

# Y = Y[0:100]
# 
time = np.arange(len(Y)) / Fs

plt.figure(figsize=(10, 4))
plt.plot(time, Y, label="Audio Signal")
plt.xlabel("Time (seconds)")
plt.ylabel("Amplitude")
plt.title(f"Waveform (Sampling Rate: {Fs} Hz)")
plt.legend()
plt.grid()
plt.show()