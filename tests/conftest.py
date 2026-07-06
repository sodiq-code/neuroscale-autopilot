"""
Pytest configuration — sets environment variables for all tests.
"""
import os
import pytest


def pytest_configure(config):
    """Set up mock environment variables before any test imports."""
    os.environ.setdefault("QWEN_API_KEY", "mock-api-key-for-testing")
    os.environ.setdefault("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    os.environ.setdefault("DRY_RUN", "true")
    os.environ.setdefault("KUBECONFIG", "/nonexistent/.kube/config")
