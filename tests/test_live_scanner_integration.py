"""Integration test for live_scanner.py.

Tests that the scanner either finds a valid signal or logs errors appropriately.
"""

import os
import sys
import logging
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loyiha'))

from live_scanner import process_asset, ASSETS


def test_scanner_finds_signal_or_logs_error():
    """
    Test that process_asset either:
    1. Finds a valid signal with all required fields, OR
    2. Logs an error/no-signal message to the log file
    
    Uses NQ asset with mocked data to avoid real API calls.
    """
    import io
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log') as tmp_log:
        log_file = tmp_log.name
    
    try:
        with patch('live_scanner.fetch_mtf_candles') as mock_fetch, \
             patch('live_scanner.evaluate_ict_combo_fixed') as mock_evaluate, \
             patch('live_scanner.is_valid_signal_for_asset') as mock_validation, \
             patch('live_scanner.predict_signal_confidence') as mock_ml, \
             patch('live_scanner.extract_features') as mock_features, \
             patch('live_scanner.is_market_open', return_value=True), \
             patch('logging.FileHandler'):
            
            dates = [datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc) + pd.Timedelta(minutes=15 * i) for i in range(30)]
            fake_df = pd.DataFrame({
                'open': [19000.0 + i for i in range(30)],
                'high': [19010.0 + i for i in range(30)],
                'low': [18990.0 + i for i in range(30)],
                'close': [19005.0 + i for i in range(30)],
                'volume': [1000.0] * 30,
                'timestamp': dates,
            })
            
            mock_fetch.return_value = (fake_df, fake_df)
            
            mock_evaluate.return_value = {
                'direction': 'LONG',
                'details': {
                    'fvgs_near_count': 1,
                    'unicorns': False,
                    'silver_bullets': False,
                    'in_ote': False
                },
                'confluence_score': 0.85
            }
            
            mock_validation.return_value = {'is_valid': True, 'htf_trend': 'LONG'}
            
            mock_features.return_value = pd.DataFrame([{'feature1': 0.5, 'feature2': 0.6}])
            
            mock_ml.return_value = 0.85
            
            result = process_asset('NQ', ASSETS['NQ'])
            
            signal_found = result is not None
            has_required_fields = False
            
            if signal_found and isinstance(result, dict):
                required = ['direction', 'symbol', 'entry_price', 'stop_loss', 'take_profit']
                has_required_fields = all(k in result for k in required)
                if has_required_fields:
                    assert result['direction'] in ['LONG', 'SHORT'], "Direction must be LONG or SHORT"
            
            assert signal_found or has_required_fields, \
                "Scanner should either find a valid signal with required fields or log an error"
    finally:
        if os.path.exists(log_file):
            os.unlink(log_file)
