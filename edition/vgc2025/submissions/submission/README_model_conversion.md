# Model Conversion to NumPy-Only Format

This directory contains tools to convert scikit-learn based evaluation models to a NumPy-only format that doesn't
require scikit-learn for inference.

## Files

- `convert_model_to_numpy.py`: Conversion script that extracts model parameters from sklearn models
- `numpy_inference.py`: NumPy-only inference implementation with automatic format detection
- `evaluation_model.pkl`: Original sklearn-based model (requires sklearn)
- `evaluation_model_numpy.pkl`: Converted NumPy-only model (no sklearn dependency)

## Usage

### Convert existing sklearn model to NumPy format:

```bash
python submission/convert_model_to_numpy.py
```

This will:

1. Load the sklearn model from `evaluation_model.pkl`
2. Extract coefficients, intercept, and other parameters
3. Save in NumPy-only format as `evaluation_model_numpy.pkl`
4. Verify the conversion accuracy

### Use the model in your code:

```python
from numpy_inference import load_model_numpy_only, predict_winner_numpy

# Automatically loads NumPy format if available, falls back to sklearn format
model, normalization_params, metrics = load_model_numpy_only("submission/evaluation_model.pkl")

# Make predictions
predicted_winner, confidence = predict_winner_numpy(model, normalization_params, state)
```

## Benefits

- **No sklearn dependency**: The NumPy-only format can be loaded and used without scikit-learn
- **Same accuracy**: Identical predictions to the original sklearn model
- **Automatic fallback**: Code works with both formats transparently
- **Smaller dependencies**: Only requires NumPy for inference

## Model Format

The NumPy-only format stores:

- Model coefficients and intercept as NumPy arrays
- Normalization parameters (mean, std)
- Model metadata and metrics
- No sklearn objects

## Verification

The conversion script includes verification that ensures:

- Predictions match exactly between sklearn and NumPy versions
- Probabilities are numerically identical (within 1e-10 tolerance)
- Model can be loaded without sklearn imports