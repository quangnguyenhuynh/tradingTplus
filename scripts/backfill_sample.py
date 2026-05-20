# scripts/backfill_sample.py
import sys
sys.path.append('.')

from src.pipeline.backfill import backfill

# Chỉ lấy 4 mã
symbols = ['SSI']

# Lấy từ 01/01/2023 đến 22/04/2026
backfill("2026-01-01", "2026-01-31", symbols)