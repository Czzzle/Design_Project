import numpy as np
import scipy.io.wavfile as wav
import matplotlib.pyplot as plt
from numpy import polyfit
from scipy.optimize import curve_fit

def cal_sin():
    '''
    Calculate the mean period by zero crossings at rising edge to get actual mean frequency
    '''
    Fs_tx, Yt = wav.read('./wavefile/12.0kHz_1000Hz_sine.wav')
    Yt = Yt/np.iinfo(np.int16).max  # Normalize to [-1, 1]

    # Find zero-crossing indices (rising edges)
    zero_crossings_tx = np.where((Yt[:-1] < 0) & (Yt[1:] >= 0))[0]
    
    # Calculate time between consecutive zero-crossings
    t_diff_tx = np.diff(zero_crossings_tx) / Fs_tx
    period_tx = np.mean(t_diff_tx)                # Average period (seconds)
    f_tx = 1 / period_tx                          # Measured frequency (Hz) for tx

    # Same for RX
    Fs_rx, Yr = wav.read('output_12k_1000.wav')
    Yr = Yr/np.iinfo(np.int16).max  # Normalize to [-1, 1]

    # Find zero-crossing indices (rising edges)
    zero_crossings_rx = np.where((Yr[:-1] < 0) & (Yr[1:] >= 0))[0]

    # Calculate time between consecutive zero-crossings
    t_diff_rx = np.diff(zero_crossings_rx) / Fs_rx
    period_rx = np.mean(t_diff_rx)                # Average period (seconds)
    f_rx = 1 / period_rx                          # Measured frequency (Hz) for rx

    print(f"transmit frequency: {f_tx}")
    print(f"receive frequency: {f_rx}")

    print( ((f_tx/f_rx)-1) * 2 / ((f_tx/f_rx)+1) ) # order of magnitude 
    diff_f = f_tx-f_rx
    print(f"Time for 1 period off: {1/diff_f} seconds")

def fit_sine_over_sliding_windows(signal, Fs, sine_freq=1000, periods_per_window=5, step_ratio=0.5, return_mse=False):
    """
    Fit a sine wave over sliding windows of multiple periods.
    
    Parameters:
    - signal: 1D numpy array of the signal
    - Fs: Sampling rate (Hz)
    - sine_freq: Approximate sine wave frequency (Hz)
    - periods_per_window: How many full cycles per window (default = 5)
    - step_ratio: Sliding window step size as a ratio of window size (e.g., 0.5 = 50% overlap)
    - return_mse: If True, return MSE per window too

    Returns:
    - freqs: list of estimated frequency per window
    - phases: list of estimated phase (radians)
    - (optional) mses: list of MSE per window
    """
    samples_per_period = Fs / sine_freq
    window_size = int(samples_per_period * periods_per_window)
    step_size = int(window_size * step_ratio)
    
    freqs = []
    phases = []
    mses = []

    def sine_func(n, A, f, phi, C):
        return A * np.sin(2 * np.pi * f * n / Fs + phi) + C

    for start in range(0, len(signal) - window_size, step_size):
        y = signal[start : start + window_size]
        n = np.arange(len(y))

        try:
            params, _ = curve_fit(sine_func, n, y, p0=[1.0, sine_freq, 0.0, 0.0])
            A, f, phi, C = params
            freqs.append(f)
            phases.append(phi)
            if return_mse:
                fitted = sine_func(n, *params)
                mse = np.mean((y - fitted) ** 2)
                mses.append(mse)
        except RuntimeError:
            freqs.append(np.nan)
            phases.append(np.nan)
            if return_mse:
                mses.append(np.nan)

    if return_mse:
        return freqs, phases, mses
    else:
        return freqs, phases

def fit_whole_sine(wav_path, f0_guess):
    Fs, y = wav.read(wav_path)
    y = y.astype(np.float64) / np.iinfo(y.dtype).max          # normalize
    n = np.arange(len(y))                                     # sample index

    def sine_func(n, A, f, phi, C):
        return A * np.sin(2*np.pi*f*n/Fs + phi) + C

    # A, f, phi,  C  — initial guesses
    p0 = [np.ptp(y)/2, f0_guess, 0.0, np.mean(y)] #np.ptp - peak to peak

    params, _ = curve_fit(sine_func, n, y, p0=p0, maxfev=8000)
    A, f_est, phi, C = params
    return f_est, params


# output_wavfile = "./wavefile/bulk_receive/12k_1.2kHz.wav"
output_wavfile = "output.wav"
f0_guess = 18000

f_est, params = fit_whole_sine(output_wavfile, f0_guess)
A, f_est, phi, C = params
print(f"Estimated frequency: {f_est:.3f} Hz")

f_nom = f0_guess

diff_f   = f_est - f_nom
skew_ratio = diff_f / f_nom
skew_ppm   = skew_ratio * 1000000 
T_slip   = 1 / diff_f
print(f"One cycle slip every {T_slip:.1f} s")

# ppm - 0.0001% shift
print(f"clock skew: {skew_ppm:+.3f} ppm")

# if __name__ == "__main__":
#     input_wavfile = "./wavefile/12.0kHz_1000Hz_sine.wav"
#     output_wavfile = "./wavefile/bulk_receive/12k_1.2kHz.wav"
#     Fs_rx, rx = wav.read(output_wavfile)
#     rx = rx.astype(np.uint16)
#     rx = rx / np.iinfo(np.uint16).max
#     freqs, phases, mses = fit_sine_over_sliding_windows(
#     signal=rx, 
#     Fs=Fs_rx, 
#     sine_freq=1200, 
#     periods_per_window=5, 
#     step_ratio=0.2,
#     return_mse=True
#     )
#     print(np.min(freqs))
#     print(np.max(freqs))
#     print(np.mean(freqs))

#     plt.figure(figsize=(10, 4))
#     plt.plot(freqs, marker='o')
#     plt.title("Smoothed Frequency Estimates (5-Period Sliding Window)")
#     plt.xlabel("Window Index")
#     plt.ylabel("Estimated Frequency (Hz)")
#     plt.grid(True)
#     plt.tight_layout()
#     plt.show()
    # square_wave_check()
    # sine_wave_drift_check()
    # cal_sin()
