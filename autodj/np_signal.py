"""
Pure NumPy Signal Processing Utilities (v9.0.0).
Replacement for scipy.signal to avoid hangups in restricted environments.
"""
import numpy as np

def get_butter_coeffs(cutoff, sr, btype='lowpass', order=4):
    """
    Calculates Butterworth filter coefficients (Biquad / SOS).
    Ref: https://en.wikipedia.org/wiki/Butterworth_filter
    """
    # For Version 9.0.0, we use a simple Biquad approximation (A-Weighting style)
    # in pure NumPy to ensure zero-hang startup.
    # In a full production environment, this would use the Bilinear Transform.
    # For now, we use a First-Order IIR for speed and stability.
    
    nyquist = 0.5 * sr
    f = cutoff / nyquist
    
    if btype == 'lowpass':
        # Simple exponential smoothing as a low-pass approximation
        alpha = f / (f + 1)
        # b, a coefficients
        return np.array([alpha]), np.array([1.0, alpha - 1.0])
    else:
        # High-pass approximation
        alpha = 1.0 / (f + 1)
        return np.array([alpha, -alpha]), np.array([1.0, alpha - 1.0])

def apply_iir_filter(data, b, a):
    """
    Applies a Direct Form I IIR filter using NumPy.
    data: (channels, samples) or (samples,)
    """
    if data.ndim == 2:
        out = np.zeros_like(data)
        for ch in range(data.shape[0]):
            out[ch] = _apply_iir_1d(data[ch], b, a)
        return out
    else:
        return _apply_iir_1d(data, b, a)

def _apply_iir_1d(x, b, a):
    # Pure numpy implementation of lfilter (Direct Form I)
    y = np.zeros_like(x)
    for n in range(len(x)):
        # y[n] = (b[0]*x[n] + b[1]*x[n-1] + ...) - (a[1]*y[n-1] + a[2]*y[n-2] + ...)
        acc = b[0] * x[n]
        if n > 0:
            if len(b) > 1: acc += b[1] * x[n-1]
            acc -= a[1] * y[n-1]
        y[n] = acc
    return y

def fast_correlate(o_k, i_k):
    """Simple sliding dot product for kick alignment."""
    # We only care about finding the peak near the center
    # This is a lightweight replacement for scipy.signal.correlate
    return np.correlate(o_k, i_k, mode='full')
