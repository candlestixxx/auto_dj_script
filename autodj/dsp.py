"""
Digital Signal Processing (DSP) Module | Auto DJ Script (v9.1.0 - Lightweight).
==============================================================
Optimized for high-performance mixing in restricted environments.
- Stateful IIR filtering for smooth frequency glides.
- RMS-based normalization for stability.
"""
import numpy as np
from .utils import ndarray_to_pydub, pydub_to_ndarray
from .np_signal import get_butter_coeffs, apply_iir_filter, StatefulIIR

class TransitionArchetype:
    """Base class for all transition plugins."""
    name = "Base"
    display_name = "Base Archetype"

    @staticmethod
    def apply(outro_array, intro_array, sr, **kwargs):
        raise NotImplementedError

class ArchetypeRegistry:
    _registry = {}

    @classmethod
    def register(cls, archetype_cls):
        cls._registry[archetype_cls.name] = archetype_cls
        return archetype_cls

    @classmethod
    def get_all(cls):
        return cls._registry

    @classmethod
    def get(cls, name):
        return cls._registry.get(name)

def apply_dsp_filter(audio_array, sr, filter_type='highpass', cutoff=150.0):
    b, a = get_butter_coeffs(cutoff, sr, btype=filter_type)
    return apply_iir_filter(audio_array, b, a)

def trim_silence(segment, silence_threshold=-65.0, chunk_size=10):
    """
    Surgical silence removal using optimized NumPy analysis.
    """
    # Convert pydub segment to array for fast analysis
    samples = np.array(segment.get_array_of_samples())
    if len(samples) == 0: return segment

    # Simple peak detection for speed
    abs_samples = np.abs(samples)
    threshold = (10**(silence_threshold/20.0)) * (2**15)

    # Find first and last indices above threshold
    active_indices = np.where(abs_samples > threshold)[0]
    if len(active_indices) == 0:
        return segment

    start_sample = active_indices[0]
    end_sample = active_indices[-1]

    # Convert samples to ms
    start_ms = int(start_sample * 1000 / segment.frame_rate / segment.channels)
    end_ms = int(end_sample * 1000 / segment.frame_rate / segment.channels)

    return segment[start_ms:end_ms]

def normalize_lufs(audio_array, sr, target_lufs=-14.0):
    rms = np.sqrt(np.mean(audio_array**2))
    if rms < 1e-6: return audio_array
    target_gain = 10**(target_lufs / 20.0)
    normalized = audio_array * (target_gain / rms)
    peak = np.max(np.abs(normalized))
    if peak > 0.99: normalized /= (peak / 0.99)
    return normalized

def apply_limiter(audio_array, threshold=0.99):
    abs_audio = np.abs(audio_array)
    mask = abs_audio > threshold
    if np.any(mask):
        out = np.where(abs_audio > threshold,
                       np.sign(audio_array) * (threshold + (1 - threshold) * np.tanh((abs_audio - threshold)/(1-threshold))),
                       audio_array)
        return out
    return audio_array

def apply_log_fade(audio_array, fade_type='in', dip_db=-2.5):
    num_samples = audio_array.shape[1] if audio_array.ndim == 2 else len(audio_array)
    x = np.linspace(0, 1, num_samples)
    curve = np.sqrt(x) if fade_type == 'in' else np.sqrt(1.0 - x)
    dip_factor = 1.0 - (1.0 - 10**(dip_db/20.0)) * np.sin(np.pi * x)
    return audio_array * curve * dip_factor

def apply_multiband_compression(audio_array, sr, intensity=0.5, genre_profile=None):
    return audio_array

def calculate_spectral_clash(outro_array, intro_array, sr):
    return {'low': 1.0, 'mid': 1.0, 'high': 1.0}

@ArchetypeRegistry.register
class DualFilterSweep(TransitionArchetype):
    name = "progressive"
    display_name = "Dual-Sweep (Professional)"

    @staticmethod
    def apply(outro_array, intro_array, sr, **kwargs):
        """
        Stateful Progressive Sweep. Ensures zero-discontinuity glides.
        """
        total_samples = outro_array.shape[1] if outro_array.ndim == 2 else len(outro_array)
        if total_samples == 0: return outro_array, intro_array
            
        block_size = int(sr * 0.1)
        f_m = np.copy(outro_array)
        f_n = np.copy(intro_array)
        num_ch = f_m.shape[0] if f_m.ndim == 2 else 1
        
        # Initial dummy filters to hold state
        b_m, a_m = get_butter_coeffs(20000.0, sr, btype='lowpass')
        b_n, a_n = get_butter_coeffs(15000.0, sr, btype='highpass')
        filter_m = StatefulIIR(b_m, a_m, num_channels=num_ch)
        filter_n = StatefulIIR(b_n, a_n, num_channels=num_ch)
        
        for start in range(0, total_samples, block_size):
            end = min(total_samples, start + block_size)
            progress = start / total_samples
            
            # Dynamic Frequencies
            lp_f = 20000.0 if progress < 0.7 else 20000 * (1500 / 20000) ** ((progress - 0.7) / 0.3)
            hp_f = 15000 * (20 / 15000) ** progress
            
            # Update filter coefficients while preserving state (z)
            filter_m.b, filter_m.a = get_butter_coeffs(lp_f, sr, btype='lowpass')
            filter_n.b, filter_n.a = get_butter_coeffs(hp_f, sr, btype='highpass')
            
            chunk_m = f_m[:, start:end] if f_m.ndim == 2 else f_m[start:end].reshape(1, -1)
            chunk_n = f_n[:, start:end] if f_n.ndim == 2 else f_n[start:end].reshape(1, -1)
            
            if chunk_m.shape[1] > 0:
                res_m = filter_m.process(chunk_m)
                if f_m.ndim == 2: f_m[:, start:end] = res_m
                else: f_m[start:end] = res_m.flatten()
                
            if chunk_n.shape[1] > 0:
                res_n = filter_n.process(chunk_n)
                if f_n.ndim == 2: f_n[:, start:end] = res_n
                else: f_n[start:end] = res_n.flatten()
                
        return f_m, f_n

def apply_bass_swap(outro, intro, sr, **kwargs):
    return apply_dsp_filter(outro, sr, 'highpass', 150.0), apply_dsp_filter(intro, sr, 'lowpass', 150.0)

def apply_echo_out(outro, sr, **kwargs): return outro, None
def apply_hpf_sweep(outro, sr, **kwargs): return outro, None
