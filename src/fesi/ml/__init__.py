"""ML layer — feature extraction, model training, inference.

Phase 3 deliverables:
  features.py   — extract feature vectors from signals + outcomes
  train.py      — train gradient-boosted scoring model (XGBoost / LightGBM)
                  on accumulated shadow data; runs on RunPod GPU when needed
  inference.py  — wrap trained model for use by the scoring layer
  calibration.py — calibration plots, A/B against the LLM-only scorer
"""
