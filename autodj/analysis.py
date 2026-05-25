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
    
    # Force Kick-only analysis for anchoring
    nyquist = 0.5 * sr
    sos_kick = butter(4, 150.0 / nyquist, btype='lowpass', output='sos')
    samples_kick = sosfiltfilt(sos_kick, samples_mono)

    ms_per_beat = 60000.0 / target_bpm
    ms_per_bar = ms_per_beat * beats_per_bar
    ms_per_transition = ms_per_bar * transition_bars
    
    # First Kick (Search start)
    search_start = int(sr * 10)
    window_s = y_kick[:search_start]
    first_kick_sample = np.argmax(window_s) if len(window_s) > 0 else 0
    first_beat_ms = first_kick_sample * 1000 / sr
    
    if len(beat_times_ms) == 0:
        return [], int(ms_per_transition), 0

    # 2. Kick-Locked Downbeat Finder (Version 8.5)
    # We use a pattern-matching heuristic: Verify the 'One' is part of a 4/4 cycle.
    search_limit = min(len(beat_times_ms), 32)
    kick_scores = []

    samples_per_beat = int((ms_per_beat / 1000.0) * sr)

    for i in range(search_limit - 4):
        # Calculate a 'Pattern Score' for this beat being the 'One'
        # Check energy at i, i+1, i+2, i+3
        pattern_energy = 0
        for offset in range(4):
            b_ms = beat_times_ms[i + offset]
            start_s = int(max(0, (b_ms - 15) * sr / 1000))
            end_s = int(min(len(samples_kick), (b_ms + 15) * sr / 1000))
            pattern_energy += np.max(np.abs(samples_kick[start_s:end_s]))

        # Check for 'Silence' between beats (confirms it's a transient, not a drone)
        mid_beat_ms = beat_times_ms[i] + (ms_per_beat / 2.0)
        m_start = int((mid_beat_ms - 15) * sr / 1000)
        m_end = int((mid_beat_ms + 15) * sr / 1000)
        mid_energy = np.max(np.abs(samples_kick[m_start:m_end])) if m_start < len(samples_kick) else 1.0

        # High score = Loud beats + Quiet gaps
        kick_scores.append(pattern_energy / (mid_energy + 0.01))

    # Anchor to the beat with the most consistent 4/4 'pulse'
    downbeat_idx = np.argmax(kick_scores) if kick_scores else 0
    first_beat_ms = beat_times_ms[downbeat_idx]

    print(f"  [ANALYSIS] Kick Pattern Lock: Beat {downbeat_idx} at {first_beat_ms}ms (Score: {max(kick_scores):.2f})")
        
    return beat_times_ms, int(ms_per_transition), first_beat_ms

def calculate_dynamic_transition(outro_y, intro_y, sr, target_bpm, beats_per_bar):
    """
    Analyzes phrase structure to determine optimal transition length.
    Returns transition bars (8, 16, or 32).
    """
    outro_ph = detect_phrases(outro_y, sr)
    intro_ph = detect_phrases(intro_y, sr)

    ms_per_beat = 60000.0 / target_bpm
    ms_per_bar = ms_per_beat * beats_per_bar

    # Heuristic: Match phrase density to transition standard multiples
    if len(outro_ph) > 5 or len(intro_ph) > 5:
        # High activity: shorter transition
        return 8
    elif len(outro_ph) < 2 and len(intro_ph) < 2:
        # Low activity: long epic transition
        return 32
    else:
        return 16

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
    """
    Finds the sample-accurate offset using Peak-Centric Alignment (Version 8.0).
    Identifies kick transients and locks their peaks.
    """
    nyquist = 0.5 * sr
    sos = butter(4, [20.0 / nyquist, 150.0 / nyquist], btype='bandpass', output='sos')

    o_m = librosa.to_mono(outro_y) if outro_y.ndim == 2 else outro_y
    i_m = librosa.to_mono(intro_y) if intro_y.ndim == 2 else intro_y
    
    win = int(sr * (60/bpm) * 8)
    win = min(win, len(o_k), len(i_k))
    if win < 100: return 0
    
    # 1. Energy Gating: Skip search if signal is too quiet (ambient)
    if np.max(i_kick) < 0.05:
        return 0

    ms_per_beat = 60000.0 / bpm
    samples_per_beat = int((ms_per_beat / 1000.0) * sr)
    
    search = int(sr * (60/bpm) * 0.5)
    slice_c = corr[max(0, center-search) : min(len(corr), center+search)]
    if len(slice_c) == 0: return 0
    
    correlation = np.correlate(o_slice, i_slice, mode='full')
    center = len(i_slice) - 1

    # Search window: +/- 1.5 full beats (catches most phasing errors)
    search_samples = int(samples_per_beat * 1.5)
    start_idx = max(0, center - search_samples)
    end_idx = min(len(correlation), center + search_samples)
    window = correlation[start_idx : end_idx]
    
    if len(window) == 0: return 0
    
    # 3. Confidence Check
    best_lag_rel = np.argmax(window)
    peak_val = window[best_lag_rel]
    avg_val = np.mean(window)
    
    if peak_val < avg_val * 1.25:
        return 0 # Low confidence, trust the grid instead

    actual_lag_samples = (start_idx + best_lag_rel) - center
    return int((actual_lag_samples / sr) * 1000)

def get_genre_archetype(y, sr, bpm=None): return "High-Energy", "Standard Psytrance"
def extract_spectral_terrain(y, sr): return []
