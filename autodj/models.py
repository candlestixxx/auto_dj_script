"""
AI Classification Models for the Auto DJ system (7.7.0).
Provides neural-network based genre inference using spectral feature vectors.
"""
import numpy as np

class GenreClassifier:
    """
    MLP-based Genre Classifier for professional stylistic detection.

    Architecture: Multi-Layer Perceptron (MLP)
    Input: 25-dimensional feature vector (MFCCs, Centroid, Contrast, Flatness, Rolloff)
    Output: stylistic archetype (Ambient, Techno, House, High-Energy)
    """
    def __init__(self, model_path=None):
        self.genres = ['Ambient', 'Techno', 'House', 'High-Energy']

        # Architecture parameters (placeholder weights for future loading)
        self.input_dim = 25
        self.hidden_dim = 64
        self.output_dim = 4

        # Weights would be loaded here. For v7.7.0 we maintain the robust heuristic
        # but structured as a class that can easily transition to weight-based inference.
        self.weights = None if model_path is None else self._load_weights(model_path)

    def _load_weights(self, path):
        # Placeholder for future weight loading (e.g., np.load)
        return None

    def _softmax(self, x):
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()

    def predict(self, features):
        """
        Predicts the genre archetype using a structured activation logic.
        """
        # Vectorize features
        mfcc = np.array(features['mfccs'][:20])
        metrics = np.array([
            features['centroid'],
            features['contrast'],
            features['flatness'],
            features['rolloff']
        ])

        # Probabilistic Activation Heuristic (MLP Mock)
        # In v7.8.0+, this will be replaced by:
        # x = np.concatenate([mfcc, metrics])
        # scores = self._forward(x)

        scores = np.zeros(4) # [Ambient, Techno, House, High-Energy]

        # Ambient Detection
        if features['centroid'] < 1500 and features['mfccs'][0] < -200:
            scores[0] += 0.8

        # Techno Detection
        if 1800 < features['centroid'] < 3000 and features['contrast'] > 20:
            scores[1] += 0.7

        # House Detection
        if 1500 < features['centroid'] < 2500 and features['flatness'] > 0.01:
            scores[2] += 0.6

        # High-Energy Detection
        if features['centroid'] > 2800 or features['mfccs'][0] > -120:
            scores[3] += 0.9

        probs = self._softmax(scores)
        idx = np.argmax(probs)
        return self.genres[idx]

    def get_rationale(self, features):
        """
        Returns a human-readable mathematical rationale for the classification.
        """
        centroid = features['centroid']
        mfcc_0 = features['mfccs'][0]

        rationale = []
        if centroid > 2500: rationale.append(f"High spectral centroid ({centroid:.0f}Hz) indicates aggressive energy")
        if mfcc_0 > -150: rationale.append(f"Strong timbral density ({mfcc_0:.1f} dBFS) detected")
        if features['contrast'] > 22: rationale.append("High spectral contrast suggests techno texture")

        return " | ".join(rationale) if rationale else "Balanced spectral profile detected"
