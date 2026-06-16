# Signal Platform ML Pipeline Documentation

## Overview

The signal platform has been enhanced with a complete machine learning pipeline that enables:
1. Continuous performance metrics collection and analysis
2. Feature extraction from trading signals and journal entries
3. Model training for trade outcome prediction and realized R estimation
4. Model inference for real-time predictions on new signals
5. Time-based train/test validation to prevent data leakage

## Architecture

### 1. Metrics Module (`signal_platform/metrics.py`)

**Purpose**: Compute quantitative metrics from journal entries

**Key Functions**:
- `compute_strategy_metrics(entries)` - Aggregate and grouped metrics
- `performance_summary_text(summary)` - Human-readable performance report
- `confidence_interval_proportion()` - Statistical confidence intervals for win rates
- `probability_of_ruin_approx()` - Risk assessment metric

**Metrics Computed**:
- Summary: win rate, payoff ratio, expectancy, total R, probability of ruin
- Grouped by: scenario, quality_grade, asset_class, time_of_day
- Each group includes full statistics

**Integration**: Called in `signal_platform/runtime.py` during route execution to enrich summaries

### 2. Feature Extraction Module (`signal_platform/ml_features.py`)

**Purpose**: Convert journal entries into machine learning feature vectors

**Key Classes**:
- `FeatureVector`: Dataclass containing features, labels, and metadata
- Feature extraction from:
  - Raw signal properties (level_distance, fwm_score, etc.)
  - Time features (hour, day_of_week, time_of_day bucket)
  - Quality scores and grades
  - Previous outcome aggregates (win ratio, avg R from recent trades)
  
**Time-Based Split**: 
- Prevents temporal data leakage
- Most recent `test_fraction` (default 20%) used as test set
- Older data used for training

**Key Functions**:
- `build_feature_vectors(entries, test_fraction=0.2)` - Create vectors with time split
- `vectors_to_numpy(vectors)` - Convert to numpy arrays for sklearn
- `load_and_build_features(journal_path)` - End-to-end loading and processing

### 3. Model Training Module (`signal_platform/ml_models.py`)

**Purpose**: Train and validate binary classification and regression models

**Models**:
1. **Outcome Classifier** (Binary)
   - Input: Feature vectors
   - Output: Win (1) or Loss (0)
   - Options: Logistic Regression, Decision Tree
   - Includes class balancing and feature scaling
   
2. **Realized R Regressor**
   - Input: Feature vectors
   - Output: Predicted realized R value
   - Model: Decision Tree with regularization
   - Metrics: MAE, RMSE, MSE

**Training Features**:
- Automatic feature scaling with StandardScaler
- Class weight balancing for imbalanced data
- Train/test evaluation with multiple metrics
- Model wrapping for transparent preprocessing
- Model persistence with joblib
- Metadata persistence with JSON

**Key Functions**:
- `train_outcome_classifier()` - Train binary classifier
- `train_realized_r_regressor()` - Train regression model
- `save_model()` / `load_model()` - Persist with joblib
- `save_model_metadata()` / `load_model_metadata()` - Persist training info

### 4. Model Inference Module (`signal_platform/ml_inference.py`)

**Purpose**: Load trained models and make predictions on new data

**Key Classes**:
- `ModelPredictor`: Load models from directory and make predictions

**Capabilities**:
- Graceful handling of missing models
- Outcome prediction with confidence scores
- Realized R prediction
- Combined prediction for both models

**Key Functions**:
- `predict_outcome(features)` - Predict trade outcome
- `predict_realized_r(features)` - Predict realized R
- `predict_both(features)` - Combined prediction
- `load_and_predict()` - Convenience function

### 5. Runtime Integration (`signal_platform/runtime.py`)

**Enhancements**:
1. **Metrics Computation**
   - Compute journal metrics on each route execution
   - Add to route summary with all grouped breakdowns
   - Add performance text for human readability
   
2. **ML Model Training**
   - Function `_train_route_ml_models()` trains models if sufficient data
   - Models saved to `{output_dir}/ml_models/`
   - Metadata saved alongside models
   - Training results included in route summary
   
3. **Health Snapshot Enrichment**
   - Added performance metrics to health snapshots
   - Win rate, expectancy, payoff ratio, ruin risk
   - Better operational visibility

4. **Summary Enrichment**
   - All grouped metrics included in route summary JSON
   - Performance breakdown by scenario, quality, asset, time
   - Model training status and results

## Workflow

### Training Pipeline

1. **Route Execution**
   ```
   run_route() → compute_strategy_metrics() 
             → _train_route_ml_models() (async, if sufficient data)
   ```

2. **Model Training**
   ```
   Journal entries → Build feature vectors (time-split)
                  → Scale features
                  → Train classifier (logistic/tree)
                  → Train regressor (tree)
                  → Save models + metadata
   ```

### Prediction Pipeline

1. **Load Models**
   ```
   ModelPredictor(model_dir) → Loads outcome + realized_r models
   ```

2. **Score New Signal**
   ```
   Signal → Extract features → Predict outcome confidence
                             → Predict realized R
   ```

## Data Flow

```
Journal Entry
    ↓
[Feature Extraction]
  - raw_signal fields (10+)
  - quality_score, quality_grade
  - time features (hour, day, bucket)
  - previous outcome stats (5 recent trades)
  ↓
Feature Vector (30+ dimensions)
    ↓
[Time-Based Split]
  - 80% training (older entries)
  - 20% test (recent entries)
    ↓
[Model Training]
  ├─ Logistic Regression → Outcome classifier (pickle)
  ├─ Decision Tree → Outcome classifier (pickle)
  └─ Decision Tree → Realized R regressor (pickle)
    ↓
[Model Metadata]
  - Feature names
  - Train/test metrics
  - Model version
    ↓
[Inference]
  New signal features → Load models → Predict outcome + R
```

## Key Design Decisions

1. **Time-Based Split**: Prevents temporal data leakage by using recent entries as test set
2. **Feature Scaling**: StandardScaler applied internally in wrapped models
3. **Class Balancing**: Binary classifiers use `class_weight='balanced'` for imbalanced data
4. **Graceful Degradation**: Inference handles missing models without crashing
5. **Metadata Persistence**: Models stored with training metrics for auditability
6. **Modular Architecture**: Each component (metrics, features, models, inference) independent

## Testing

All components have comprehensive test coverage:

- **Feature Extraction Tests** (5 tests)
  - Raw signal feature extraction
  - Time feature extraction
  - Previous outcome computation
  - Feature vector building
  - NumPy array conversion

- **Model Training Tests** (4 tests)
  - Logistic regression training
  - Decision tree training
  - Regression model training
  - Metadata persistence

- **End-to-End Tests** (4 tests)
  - Full pipeline from journal to models
  - Journal file loading
  - Model inference
  - Graceful error handling

**Test Results**: 13/13 passing

## Usage Examples

### Computing Metrics
```python
from signal_platform.metrics import compute_strategy_metrics, performance_summary_text
from signal_platform.journal import load_journal

entries = load_journal("signal_journal.json")
metrics = compute_strategy_metrics(entries)

# Grouped by scenario
by_scenario = metrics["by_scenario"]

# Performance text for reporting
text = performance_summary_text(metrics["summary"])
print(text)
```

### Training Models
```python
from signal_platform.runtime import _train_route_ml_models
from signal_platform.runtime import StrategyRoute

# Automatic during route execution
# Or manual:
route = StrategyRoute(...)
result = _train_route_ml_models(route, min_closed_samples=20)
print(result["models_trained"])  # ["outcome_classifier", "realized_r_regressor"]
```

### Using Trained Models
```python
from signal_platform.ml_inference import ModelPredictor

predictor = ModelPredictor("platform_output/strategy_four/ml_models")

features = {
    "quality_score": 8.5,
    "raw_signal_fwm_score": 0.75,
    "hour": 14,
    "time_of_day": "afternoon",
    ...
}

outcome = predictor.predict_outcome(features)
print(f"Prediction: {outcome['prediction_text']} ({outcome['confidence']:.2%})")

realized_r = predictor.predict_realized_r(features)
print(f"Expected R: {realized_r['prediction_rounded']:.2f}R")
```

## Roadmap for Future Enhancements

1. **Feature Engineering**
   - Market regime features (volatility, trend strength)
   - Recent correlation features
   - Volume/momentum proxies

2. **Advanced Models**
   - Random Forest ensembles
   - Gradient Boosting (XGBoost)
   - Neural networks for non-linear patterns

3. **Real-Time Integration**
   - Score signals at dispatch time
   - Filter or rank signals by predicted outcome
   - Dynamic position sizing based on confidence

4. **Model Monitoring**
   - Track model performance degradation
   - Automatic retraining triggers
   - Drift detection

5. **Ensemble Methods**
   - Combine outcome + realized R predictions
   - Weighted signal scoring
   - Confidence-based routing

## Files Modified/Created

**Created**:
- `signal_platform/metrics.py` - Metrics computation
- `signal_platform/ml_features.py` - Feature extraction
- `signal_platform/ml_models.py` - Model training
- `signal_platform/ml_inference.py` - Model inference
- `tests/test_signal_platform_ml.py` - Comprehensive tests

**Modified**:
- `signal_platform/runtime.py` - Integration of metrics and ML training

## Dependencies

- **numpy** - Array operations
- **scikit-learn** - ML models and preprocessing
- **joblib** - Model persistence

Install with:
```bash
pip install scikit-learn numpy joblib
```

## Conclusion

The ML pipeline provides a foundation for AI-enhanced signal quality and outcome prediction. All components are:
- **Tested**: 13/13 tests passing
- **Documented**: Comprehensive docstrings and README
- **Modular**: Independent, reusable components
- **Production-Ready**: Error handling, graceful degradation
- **Extensible**: Easy to add new features, models, metrics
