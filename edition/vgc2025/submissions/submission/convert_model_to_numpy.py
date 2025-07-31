#!/usr/bin/env python3
"""
Convert sklearn-based evaluation model to NumPy-only format.
This script extracts the model parameters from the sklearn model and saves them
in a format that doesn't require sklearn for loading.
"""
import pickle

import numpy as np


def examine_model_structure(model_path: str = "submission/evaluation_model.pkl"):
    """Examine the structure of the current model file."""
    print(f"Examining model structure in {model_path}...")

    with open(model_path, "rb") as f:
        model_data = pickle.load(f)

    print("Top-level keys:", list(model_data.keys()))

    sklearn_model = model_data["model"]
    print(f"Model type: {type(sklearn_model)}")
    print(f"Model class: {sklearn_model.__class__.__name__}")

    # Extract key parameters
    print(f"Coefficients shape: {sklearn_model.coef_.shape}")
    print(f"Intercept shape: {sklearn_model.intercept_.shape}")
    print(f"Classes: {sklearn_model.classes_}")

    print(f"Normalization params keys: {list(model_data['normalization_params'].keys())}")
    print(f"Metrics keys: {list(model_data['metrics'].keys())}")
    print(f"Feature dimension: {model_data['feature_dimension']}")

    return model_data


def convert_to_numpy_format(
        input_path: str = "submission/evaluation_model.pkl",
        output_path: str = "submission/evaluation_model_numpy.pkl"
):
    """
    Convert sklearn model to NumPy-only format.
    
    Args:
        input_path: Path to sklearn model file
        output_path: Path to save NumPy-only model file
    """
    print(f"Converting {input_path} to NumPy-only format...")

    # Load sklearn model
    with open(input_path, "rb") as f:
        model_data = pickle.load(f)

    sklearn_model = model_data["model"]

    # Extract model parameters (only NumPy arrays)
    numpy_model_data = {
        "model_type": "logistic_regression",
        "model_params": {
            "coef": sklearn_model.coef_.copy(),  # Shape: (1, n_features)
            "intercept": sklearn_model.intercept_.copy(),  # Shape: (1,)
            "classes": sklearn_model.classes_.copy(),  # Should be [0, 1]
        },
        "normalization_params": model_data["normalization_params"],  # Already NumPy arrays
        "metrics": model_data["metrics"],
        "feature_dimension": model_data["feature_dimension"],
        "sklearn_info": {
            "original_class": sklearn_model.__class__.__name__,
            "n_features_in": sklearn_model.n_features_in_,
            "n_iter": sklearn_model.n_iter_,
        }
    }

    # Verify extracted parameters
    print(f"Extracted coefficients shape: {numpy_model_data['model_params']['coef'].shape}")
    print(f"Extracted intercept shape: {numpy_model_data['model_params']['intercept'].shape}")
    print(f"Extracted classes: {numpy_model_data['model_params']['classes']}")

    # Save in NumPy-only format
    with open(output_path, "wb") as f:
        pickle.dump(numpy_model_data, f)

    print(f"Converted model saved to {output_path}")

    # Verify the saved file can be loaded without sklearn
    print("Verifying saved file...")
    with open(output_path, "rb") as f:
        loaded_data = pickle.load(f)

    print("✅ Successfully saved and verified NumPy-only model format")

    return numpy_model_data


def verify_conversion(
        original_path: str = "submission/evaluation_model.pkl",
        converted_path: str = "submission/evaluation_model_numpy.pkl"
):
    """
    Verify that the converted model produces the same results as the original.
    """
    print("Verifying conversion accuracy...")

    # Test data (random features)
    np.random.seed(42)
    test_features = np.random.randn(5, 164)  # 5 samples, 164 features

    # Load original model and make predictions
    from train_evaluation_model import load_model
    sklearn_model, norm_params, _ = load_model(original_path)

    # Apply normalization
    from feature_extraction import apply_normalization
    test_features_norm = apply_normalization(test_features, norm_params)

    # Original predictions
    original_pred = sklearn_model.predict(test_features_norm)
    original_proba = sklearn_model.predict_proba(test_features_norm)

    # Load converted model
    with open(converted_path, "rb") as f:
        numpy_data = pickle.load(f)

    # Create NumPy model
    from numpy_inference import NumpyLogisticRegression
    numpy_model = NumpyLogisticRegression(
        numpy_data["model_params"]["coef"][0],  # Remove outer dimension
        numpy_data["model_params"]["intercept"]
    )

    # NumPy predictions
    numpy_pred = numpy_model.predict(test_features_norm)
    numpy_proba = numpy_model.predict_proba(test_features_norm)

    # Compare results
    pred_match = np.array_equal(original_pred, numpy_pred)
    proba_close = np.allclose(original_proba, numpy_proba, rtol=1e-10)

    print(f"Predictions match: {pred_match}")
    print(f"Probabilities close (rtol=1e-10): {proba_close}")

    if pred_match and proba_close:
        print("✅ Conversion verification successful!")
        return True
    else:
        print("❌ Conversion verification failed!")
        print(f"Original predictions: {original_pred}")
        print(f"NumPy predictions: {numpy_pred}")
        print(f"Max probability difference: {np.max(np.abs(original_proba - numpy_proba))}")
        return False


if __name__ == "__main__":
    # Step 1: Examine current structure
    model_data = examine_model_structure()

    print("\n" + "=" * 50 + "\n")

    # Step 2: Convert to NumPy format
    convert_to_numpy_format()

    print("\n" + "=" * 50 + "\n")

    # Step 3: Verify conversion
    verify_conversion()
