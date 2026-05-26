""" Digital Signal Processing (DSP) Module | Auto DJ Script (v9.3.0 - Clean Transitions).
==============================================================
Professional DJ-style transitions that sound like a real DJ mixer.

Design philosophy:
- Volume crossfade does 90% of the mixing work
- Bass swap handles the kick drum transition
- No aggressive filter sweeps — those are an effect, not a transition
- A real DJ mixer has 3-band EQ (HI/MID/LO) and volume faders, nothing more
"""

import numpy as np
from .utils import ndarray_to_pydub, pydub_to_ndarray
from .np_signal import get_butter_coeffs, apply_iir_filter


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
    """Surgical silence removal using optimized NumPy analysis."""
    samples = np.array(segment.get_array_of_samples())
    if len(samples) == 0:
        return segment

    abs_samples = np.abs(samples)
    threshold = (10 ** (silence_threshold / 20.0)) * (2 ** 15)

    active_indices = np.where(abs_samples > threshold)[0]
    if len(active_indices) == 0:
        return segment

    start_sample = active_indices[0]
    end_sample = active_indices[-1]

    start_ms = int(start_sample * 1000 / segment.frame_rate / segment.channels)
    end_ms = int(end_sample * 1000 / segment.frame_rate / segment.channels)

    return segment[start_ms:end_ms]


def normalize_lufs(audio_array, sr, target_lufs=-14.0):
    rms = np.sqrt(np.mean(audio_array ** 2))
    if rms < 1e-6:
        return audio_array
    target_gain = 10 ** (target_lufs / 20.0)
    normalized = audio_array * (target_gain / rms)
    peak = np.max(np.abs(normalized))
    if peak > 0.99:
        normalized /= (peak / 0.99)
    return normalized


def apply_limiter(audio_array, threshold=0.99):
    abs_audio = np.abs(audio_array)
    mask = abs_audio > threshold
    if np.any(mask):
        out = np.where(
            abs_audio > threshold,
            np.sign(audio_array) * (threshold + (1 - threshold) * np.tanh((abs_audio - threshold) / (1 - threshold))),
            audio_array
        )
        return out
    return audio_array


def apply_multiband_compression(audio_array, sr, intensity=0.5, genre_profile=None):
    return audio_array


def calculate_spectral_clash(outro_array, intro_array, sr):
    return {'low': 1.0, 'mid': 1.0, 'high': 1.0}


def _apply_bass_swap_transition(outro_array, intro_array, sr, **kwargs):
    """The core DJ transition: bass swap + volume crossfade.

    This is how a real DJ mixes on a standard 2-channel mixer:
    1. Intro starts playing with its LOW EQ cut (bass at -inf)
    2. As the mix progresses, the intro's bass is brought in
    3. Simultaneously the outro's bass is cut
    4. The volume fader crossfades the mid/high smoothly
    5. The "bass swap" moment is where the kick drum changes over

    NO filter sweeps. NO resonant sweeps. Just EQ and faders.
    """
    out_len = outro_array.shape[1] if outro_array.ndim == 2 else len(outro_array)
    in_len = intro_array.shape[1] if intro_array.ndim == 2 else len(intro_array)
    if out_len == 0 or in_len == 0:
        return np.copy(outro_array), np.copy(intro_array)

    # --- SPECTRAL: bass management only (single filter call, no per-block) ---

    # Build separate gain curves for outro and intro (they may differ in length)
    x_out = np.linspace(0, 1, out_len)
    outro_bass_curve = np.ones(out_len)
    mask = x_out > 0.4
    outro_bass_curve[mask] = 0.5 * (1 + np.cos(np.pi * (x_out[mask] - 0.4) / 0.4))
    outro_bass_curve[x_out > 0.8] = 0.02

    x_in = np.linspace(0, 1, in_len)
    intro_bass_curve = np.zeros(in_len)
    mask = x_in > 0.3
    intro_bass_curve[mask] = 0.5 * (1 - np.cos(np.pi * (x_in[mask] - 0.3) / 0.4))
    intro_bass_curve[x_in > 0.7] = 1.0

    # Apply bass management using crossover filters
    try:
        from scipy.signal import lfilter, butter

        # Design crossover filters (2nd-order for gentle slopes)
        b_lo, a_lo = butter(2, 150.0 / (0.5 * sr), btype='low')
        b_hi, a_hi = butter(2, 150.0 / (0.5 * sr), btype='high')

        # Split and recombine each track
        f_m = np.zeros_like(outro_array)
        f_n = np.zeros_like(intro_array)

        if outro_array.ndim == 2:
            for ch in range(outro_array.shape[0]):
                bass = lfilter(b_lo, a_lo, outro_array[ch])[:out_len]
                rest = lfilter(b_hi, a_hi, outro_array[ch])[:out_len]
                f_m[ch] = rest + bass * outro_bass_curve
        else:
            bass = lfilter(b_lo, a_lo, outro_array)[:out_len]
            rest = lfilter(b_hi, a_hi, outro_array)[:out_len]
            f_m = rest + bass * outro_bass_curve

        if intro_array.ndim == 2:
            for ch in range(intro_array.shape[0]):
                bass = lfilter(b_lo, a_lo, intro_array[ch])[:in_len]
                rest = lfilter(b_hi, a_hi, intro_array[ch])[:in_len]
                f_n[ch] = rest + bass * intro_bass_curve
        else:
            bass = lfilter(b_lo, a_lo, intro_array)[:in_len]
            rest = lfilter(b_hi, a_hi, intro_array)[:in_len]
            f_n = rest + bass * intro_bass_curve

        return f_m, f_n

    except ImportError:
        # No scipy: just return unmodified -- the volume crossfade will do all the work
        return np.copy(outro_array), np.copy(intro_array)


def apply_bass_swap(outro, intro, sr, **kwargs):
    return apply_dsp_filter(outro, sr, 'highpass', 150.0), apply_dsp_filter(intro, sr, 'lowpass', 150.0)


def apply_echo_out(outro, sr, **kwargs):
    return outro, None


def apply_hpf_sweep(outro, sr, **kwargs):
    return outro, None
