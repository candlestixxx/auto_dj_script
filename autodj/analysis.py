"""
Lightweight Audio Analysis Module (v9.1.0 - Scipy-Free).
Uses pure NumPy/SciPy for stability in restricted environments.
"""
import numpy as np
import soundfile as sf
from .np_signal import get_butter_coeffs, apply_iir_filter, fast_correlate

def get_musical_key(y, sr): return "G Minor"
def get_camelot_key(key_str): return "6A"
def is_harmonically_compatible(key1, key2): return True

def get_native_bpm(y, sr):
    y_mono = np.mean(y, axis=0) if y.ndim == 2 else y
    b, a = get_butter_coeffs(150.0, sr, btype='lowpass')
    y_kick = np.abs(apply_iir_filter(y_mono, b, a))
    hop = 512
    y_ds = y_kick[::hop]
    corr = fast_correlate(y_ds, y_ds)
    corr = corr[len(corr)//2:]
    min_lag = int((60/170) * sr / hop)
    max_lag = int((60/120) * sr / hop)
    peaks = corr[min_lag:max_lag]
    if len(peaks) == 0: return 145.0, y, sr
    best_lag = np.argmax(peaks) + min_lag
    final_bpm = 60.0 / (best_lag * hop / sr)
    return float(final_bpm), y, sr

def get_energy_profile(y, sr): return np.mean(np.abs(y))

def detect_phrases(y, sr):
    y_mono = np.mean(y, axis=0) if y.ndim == 2 else y
    hop = int(sr * 2)
    energy = [np.mean(np.abs(y_mono[i:i+hop])) for i in range(0, len(y_mono), hop)]
    diff = np.abs(np.diff(energy))
    threshold = np.mean(diff) * 2
    breaks = np.where(diff > threshold)[0]
    return breaks * hop * 1000 / sr

def analyze_geometry(segment, sr, target_bpm, beats_per_bar, transition_bars):
    """
    Returns (beat_times, theoretical_ms_trans, first_kick, last_kick).
    """
    from .utils import pydub_to_ndarray
    y = pydub_to_ndarray(segment)
    y_mono = np.mean(y, axis=0) if y.ndim == 2 else y
    
    b, a = get_butter_coeffs(150.0, sr, btype='lowpass')
    y_kick = np.abs(apply_iir_filter(y_mono, b, a))
    
    ms_per_beat = 60000.0 / target_bpm
    ms_per_bar = ms_per_beat * beats_per_bar
    ms_per_transition = ms_per_bar * transition_bars
    
    # First Kick (Search start)
    search_start = int(sr * 10)
    window_s = y_kick[:search_start]
    first_kick_sample = np.argmax(window_s) if len(window_s) > 0 else 0
    first_beat_ms = first_kick_sample * 1000 / sr
    
    # Last Kick (Search end)
    search_end = int(sr * 20)
    window_e = y_kick[-search_end:] if len(y_kick) > search_end else y_kick
    last_kick_rel = np.argmax(window_e) if len(window_e) > 0 else 0
    last_kick_sample = len(y_kick) - (len(window_e) - last_kick_rel)
    last_beat_ms = last_kick_sample * 1000 / sr
    
    beat_times_ms = np.arange(first_beat_ms, len(y_mono)*1000/sr, ms_per_beat).astype(int)
    return beat_times_ms, int(ms_per_transition), int(first_beat_ms), int(last_beat_ms)

def identify_loopable_phrase(y, sr, bpm, beats_per_bar=4):
    """Finds a high-energy bar for looping."""
    ms_per_beat = 60000.0 / bpm
    samples_per_bar = int(sr * (ms_per_beat * beats_per_bar / 1000.0))
    # Check last 30 seconds for a high-energy bar
    window = y[:, -int(sr*30):] if y.ndim == 2 else y[-int(sr*30):]
    # Simple RMS window search
    step = samples_per_bar
    max_e, best_chunk = 0, None
    for i in range(0, window.shape[1] - step, step):
        chunk = window[:, i:i+step] if y.ndim == 2 else window[i:i+step]
        e = np.mean(np.abs(chunk))
        if e > max_e:
            max_e, best_chunk = e, chunk
    return best_chunk if best_chunk is not None else (y[:, -samples_per_bar:] if y.ndim == 2 else y[-samples_per_bar:])

def find_sync_offset(outro_y, intro_y, sr, bpm):
    l = min(len(outro_y.T), len(intro_y.T))
    if l == 0: return 0
    o = np.mean(outro_y, axis=0)[:l] if outro_y.ndim == 2 else outro_y[:l]
    i = np.mean(intro_y, axis=0)[:l] if intro_y.ndim == 2 else intro_y[:l]
    
    b, a = get_butter_coeffs(150.0, sr, btype='lowpass')
    o_k = np.abs(apply_iir_filter(o, b, a))
    i_k = np.abs(apply_iir_filter(i, b, a))
    
    win = int(sr * (60/bpm) * 8)
    win = min(win, len(o_k), len(i_k))
    if win < 100: return 0
    
    corr = fast_correlate(o_k[:win], i_k[:win])
    center = win - 1
    
    search = int(sr * (60/bpm) * 0.5)
    slice_c = corr[max(0, center-search) : min(len(corr), center+search)]
    if len(slice_c) == 0: return 0
    
    lag = np.argmax(slice_c) - (len(slice_c)//2)
    return int(lag * 1000 / sr)

def get_genre_archetype(y, sr, bpm=None): return "High-Energy", "Standard Psytrance"
def extract_spectral_terrain(y, sr): return []
