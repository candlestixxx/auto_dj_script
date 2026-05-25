"""
Pure NumPy Signal Processing Utilities (v9.1.0).
Replacement for scipy.signal with Stateful Filtering support.
"""
import numpy as np

class StatefulIIR:
    """
    Implements a stateful Direct Form I IIR filter.
    Preserves state (z) between calls for smooth block-based filtering.
    """
    def __init__(self, b, a, num_channels=2):
        self.b = b
        self.a = a
        self.num_channels = num_channels
        # State: [delay_line_idx, channel]
        # Direct Form I needs max(len(a), len(b)) - 1 states
        self.order = max(len(a), len(b)) - 1
        self.x_z = np.zeros((self.order, num_channels))
        self.y_z = np.zeros((self.order, num_channels))

    def process(self, chunk):
        """
        Processes a block of audio.
        chunk: (channels, samples)
        """
        if chunk.ndim == 1:
            chunk = chunk.reshape(1, -1)
        
        out = np.zeros_like(chunk)
        num_samples = chunk.shape[1]
        
        for n in range(num_samples):
            for ch in range(self.num_channels):
                # y[n] = b[0]*x[n] + b[1]*x[n-1]... - a[1]*y[n-1]...
                acc = self.b[0] * chunk[ch, n]
                
                # Feedback/Forward from state
                for i in range(1, self.order + 1):
                    x_prev = self.x_z[i-1, ch] if i <= self.order else 0
                    y_prev = self.y_z[i-1, ch] if i <= self.order else 0
                    if i < len(self.b): acc += self.b[i] * x_prev
                    if i < len(self.a): acc -= self.a[i] * y_prev
                
                out[ch, n] = acc
                
                # Update state (shift)
                if self.order > 0:
                    self.x_z = np.roll(self.x_z, 1, axis=0)
                    self.y_z = np.roll(self.y_z, 1, axis=0)
                    self.x_z[0, ch] = chunk[ch, n]
                    self.y_z[0, ch] = acc
        return out

def get_butter_coeffs(cutoff, sr, btype='lowpass'):
    """
    Calculates 1st-order IIR coefficients for stability.
    """
    nyquist = 0.5 * sr
    f = cutoff / nyquist
    if btype == 'lowpass':
        alpha = f / (f + 1)
        return np.array([alpha, alpha]), np.array([1.0, alpha - 1.0])
    else:
        alpha = 1.0 / (f + 1)
        return np.array([alpha, -alpha]), np.array([1.0, alpha - 1.0])

def apply_iir_filter(data, b, a):
    """One-shot stateless filter (wraps StatefulIIR)."""
    num_ch = data.shape[0] if data.ndim == 2 else 1
    f = StatefulIIR(b, a, num_channels=num_ch)
    return f.process(data)

def fast_correlate(o_k, i_k):
    return np.correlate(o_k, i_k, mode='full')
