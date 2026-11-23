#!/usr/bin/env python3
"""
PubCast Security Vault - Setup
"""

from setuptools import setup, find_packages

setup(
    name="pubcast-vault",
    version="0.1.0",
    description="Production-grade security vault for PubCast AI",
    author="PubCast Team",
    license="proprietary",
    python_requires=">=3.9",
    install_requires=[
        "sqlcipher3>=5.5.0",
        "cryptography>=41.0.0",
        "pydantic>=2.0.0",
    ],
    packages=find_packages(),
    scripts=[
        "pubcast_vault_cli.py",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Security",
    ],
)
