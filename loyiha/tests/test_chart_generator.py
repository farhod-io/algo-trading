import unittest
import pandas as pd
import io
from services.chart_generator import generate_signal_chart


class TestChartGenerator(unittest.TestCase):
    def test_generate_signal_chart(self):
        # Create dummy candle dataset
        dates = pd.date_range(start="2026-08-04 10:00", periods=20, freq="5min")
        df = pd.DataFrame({
            "timestamp": dates,
            "open": [2600 + i for i in range(20)],
            "high": [2605 + i for i in range(20)],
            "low": [2598 + i for i in range(20)],
            "close": [2603 + i for i in range(20)],
            "volume": [100.0] * 20
        })

        signal_info = {
            "pair": "GC",
            "direction": "LONG",
            "entry_price": 2610.0,
            "sl": 2595.0,
            "tp1": 2625.0,
            "tp2": 2640.0,
            "confidence": 85.5,
            "details": {
                "fvgs": [{"top": 2605, "bottom": 2602}]
            }
        }

        buf = generate_signal_chart(df, signal_info, max_candles=20)
        self.assertIsInstance(buf, io.BytesIO)
        buf_bytes = buf.getvalue()
        self.assertGreater(len(buf_bytes), 1000)  # Valid PNG image bytes


if __name__ == "__main__":
    unittest.main()
