"""Fetch data from external APIs."""
import os
import requests
from config import API_KEYS, COUNTIES


def fetch_data(county_name: str) -> dict:
    """Fetch all available data for a county."""
    return fetch_county_data(county_name)
