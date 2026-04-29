import pytest
from benchmark_utils import calculate_multiplier

def test_calculate_multiplier_baseline():
    """Test with baseline duration (35.0s) -> 1.0x"""
    assert calculate_multiplier(35.0) == 1.0

def test_calculate_multiplier_half_baseline():
    """Test with half baseline duration (17.5s) -> 2.0x"""
    assert calculate_multiplier(17.5) == 2.0

def test_calculate_multiplier_double_baseline():
    """Test with double baseline duration (70.0s) -> 0.5x"""
    assert calculate_multiplier(70.0) == 0.5

def test_calculate_multiplier_zero():
    """Test with zero duration -> 0.0"""
    assert calculate_multiplier(0) == 0.0

def test_calculate_multiplier_negative():
    """Test with negative duration -> 0.0"""
    assert calculate_multiplier(-1.0) == 0.0

def test_calculate_multiplier_cap():
    """Test with very small duration -> Capped at 20.0x"""
    assert calculate_multiplier(0.1) == 20.0
    assert calculate_multiplier(1.0) == 20.0 # 35/1 = 35, capped at 20

def test_calculate_multiplier_large():
    """Test with very large duration -> small value"""
    assert calculate_multiplier(3500.0) == 0.01

def test_calculate_multiplier_rounding():
    """Test rounding to 2 decimal places"""
    # 35.0 / 3.0 = 11.666666666666666 -> 11.67
    assert calculate_multiplier(3.0) == 11.67
    # 35.0 / 6.0 = 5.833333333333333 -> 5.83
    assert calculate_multiplier(6.0) == 5.83
