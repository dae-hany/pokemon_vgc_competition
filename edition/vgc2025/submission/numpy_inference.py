"""
NumPy-only inference functions to replace scikit-learn dependencies.
This module provides the same functionality as the scikit-learn LogisticRegression
model but using only NumPy operations for inference.
"""
import pickle
from typing import Any, Dict, Tuple

import numpy as np


class NumpyLogisticRegression:
    """
    NumPy-only implementation of logistic regression inference.
    Compatible with scikit-learn LogisticRegression models.
    """

    def __init__(self, coef: np.ndarray, intercept: np.ndarray):
        """
        Initialize with coefficients and intercept from a trained model.
        
        Args:
            coef: Model coefficients (shape: [n_features] for binary classification)
            intercept: Model intercept (shape: [1] for binary classification)
        """
        self.coef_ = coef.reshape(1, -1) if coef.ndim == 1 else coef
        self.intercept_ = intercept

    def _sigmoid(self, z: np.ndarray) -> np.ndarray:
        """Sigmoid activation function with numerical stability."""
        # Clip z to prevent overflow
        z = np.clip(z, -250, 250)
        return 1.0 / (1.0 + np.exp(-z))

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        """Compute the decision function (linear combination)."""
        return X @ self.coef_.T + self.intercept_

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities.
        
        Args:
            X: Input features (shape: [n_samples, n_features])
            
        Returns:
            Probabilities for each class (shape: [n_samples, 2])
        """
        decision = self.decision_function(X)
        prob_positive = self._sigmoid(decision)
        prob_negative = 1.0 - prob_positive

        # Return probabilities for both classes
        return np.column_stack([prob_negative, prob_positive])

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict binary class labels.
        
        Args:
            X: Input features (shape: [n_samples, n_features])
            
        Returns:
            Predicted class labels (0 or 1)
        """
        probabilities = self.predict_proba(X)
        return (probabilities[:, 1] >= 0.5).astype(int)


def load_model_numpy_only(filename: str = "evaluation_model.pkl") -> Tuple[
    NumpyLogisticRegression, Dict[str, np.ndarray], Dict[str, Any]]:
    """
    Load a model in NumPy-only format, with fallback to sklearn format conversion.
    
    Args:
        filename: Path to the pickled model file
        
    Returns:
        numpy_model: NumPy-only logistic regression model
        normalization_params: Feature normalization parameters
        metrics: Model evaluation metrics
    """
    # Try NumPy-only format first (preferred)
    numpy_filename = filename.replace(".pkl", "_numpy.pkl")
    if numpy_filename != filename and _try_load_numpy_format(numpy_filename):
        return _load_numpy_format(numpy_filename)

    # Fall back to original format and convert
    return _load_sklearn_format(filename)


def _try_load_numpy_format(filename: str) -> bool:
    """Check if NumPy-only format file exists and is valid."""
    try:
        import os
        if not os.path.exists(filename):
            return False

        with open(filename, "rb") as f:
            model_data = pickle.load(f)

        # Check if it's the expected NumPy format
        return (
                "model_type" in model_data and
                "model_params" in model_data and
                model_data["model_type"] == "logistic_regression"
        )
    except Exception:
        return False


def _load_numpy_format(filename: str) -> Tuple[NumpyLogisticRegression, Dict[str, np.ndarray], Dict[str, Any]]:
    """Load model from NumPy-only format."""
    with open(filename, "rb") as f:
        model_data = pickle.load(f)

    # Extract model parameters
    model_params = model_data["model_params"]
    coef = model_params["coef"][0]  # Remove outer dimension for binary classification
    intercept = model_params["intercept"]

    # Create NumPy-only model
    numpy_model = NumpyLogisticRegression(coef, intercept)

    return numpy_model, model_data["normalization_params"], model_data["metrics"]


def _load_sklearn_format(filename: str) -> Tuple[NumpyLogisticRegression, Dict[str, np.ndarray], Dict[str, Any]]:
    """Load and convert model from sklearn format (requires sklearn)."""
    with open(filename, "rb") as f:
        model_data = pickle.load(f)

    sklearn_model = model_data["model"]
    normalization_params = model_data["normalization_params"]
    metrics = model_data["metrics"]

    # Extract coefficients and intercept from scikit-learn model
    coef = sklearn_model.coef_[0]  # For binary classification
    intercept = sklearn_model.intercept_

    # Create NumPy-only model
    numpy_model = NumpyLogisticRegression(coef, intercept)

    return numpy_model, normalization_params, metrics


def predict_winner_numpy(
        model: NumpyLogisticRegression,
        normalization_params: Dict[str, np.ndarray],
        state
) -> Tuple[int, float]:
    """
    Predict winner using NumPy-only model.
    
    Args:
        model: NumPy-only logistic regression model
        normalization_params: Feature normalization parameters
        state: Game state to evaluate
        
    Returns:
        predicted_winner: Predicted winner (0 or 1)
        confidence: Prediction confidence (0.5-1.0)
    """
    from feature_extraction import apply_normalization, extract_features_from_state

    # Extract features
    features = extract_features_from_state(state).reshape(1, -1)

    # Normalize features
    features_normalized = apply_normalization(features, normalization_params)

    # Predict
    prediction = model.predict(features_normalized)[0]
    probabilities = model.predict_proba(features_normalized)[0]
    confidence = max(probabilities)

    return int(prediction), float(confidence)
