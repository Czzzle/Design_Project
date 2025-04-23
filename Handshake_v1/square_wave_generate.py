import numpy as np
from scipy.io import wavfile as wav

def gen_sharp_square_wave():
    # Set sampling rate and frequency
    sample_rate = 180000
    frequency = sample_rate//2
    # frequency = 100
    duration = 30
    
    # Compute total number of samples
    num_samples = int(sample_rate * duration)
    
    # Compute samples per cycle (one period of the square wave)
    samples_per_cycle = sample_rate // frequency

    # Create one period of the square wave (half high, half low)
    half_cycle = samples_per_cycle // 2
    square_wave = np.tile(
        np.concatenate((np.ones(half_cycle), np.zeros(half_cycle))),
        num_samples // samples_per_cycle
    )

    # Scale to 16-bit PCM format
    max_int16 = np.iinfo(np.int16).max
    scaled_wave = (square_wave * max_int16).astype(np.int16)

    # Save as a WAV file
    # ** WARINGING: Be careful about the path **
    wav.write(f'{sample_rate/1000}kHz_{frequency}Hz_square.wav', sample_rate, scaled_wave)
    print("Created successfully.")

def gen_sine_wave():
    # Set sampling rate and frequency
    sample_rate = 1000
    frequency = 100
    duration = 30

    # Compute total number of samples
    num_samples = int(sample_rate * duration)

    # Generate time values
    t = np.linspace(0, duration, num_samples, endpoint=False)

    # Generate sine wave
    sine_wave = np.sin(2 * np.pi * frequency * t)

    # Scale to 16-bit PCM format
    max_int16 = np.iinfo(np.int16).max
    scaled_wave = (sine_wave * max_int16).astype(np.int16)

    # Ensure the output directory exists

    # os.makedirs(output_dir, exist_ok=True)

    # Save as a WAV file
    filename = f'{sample_rate/1000}kHz_{frequency}Hz_{duration}_sine.wav'
    wav.write(filename, sample_rate, scaled_wave)
    print(f"Created successfully: {filename}")

if __name__ == "__main__":
    # gen_sharp_square_wave()
    gen_sine_wave()
