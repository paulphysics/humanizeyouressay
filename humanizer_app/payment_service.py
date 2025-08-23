# FILE: humanizer_app/payment_service.py
"""
This module handles interactions with the Pay Hero payment gateway and defines the application's pricing structure.
"""

import os
import requests
import json
import logging

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pay Hero API Configuration
PAY_HERO_API_URL = 'https://backend.payhero.co.ke/api/v2/payments'
PAY_HERO_BASIC_AUTH_TOKEN = os.getenv("PAY_HERO_BASIC_AUTH_TOKEN")
PAY_HERO_CHANNEL_ID = os.getenv("PAY_HERO_CHANNEL_ID")
PAY_HERO_CALLBACK_URL = os.getenv("PAY_HERO_CALLBACK_URL")

# --- CORRECTED PRICING CONSTANTS ---
WORDS_PER_UNIT = 275
PRICE_PER_UNIT = 39.0                # KSh for Standard Humanization
ESSAY_PRICE_PER_UNIT = 39.0          # KSh for Essay Humanization (now same as standard)
FORMAT_ONLY_PRICE_PER_UNIT = 19.0    # KSh for Formatting Only
# ------------------------------------

# --- Environment Variable Validation ---
def validate_env_vars():
    """Validates that all necessary environment variables are set."""
    required_vars = {
        "PAY_HERO_BASIC_AUTH_TOKEN": PAY_HERO_BASIC_AUTH_TOKEN,
        "PAY_HERO_CHANNEL_ID": PAY_HERO_CHANNEL_ID,
        "PAY_HERO_CALLBACK_URL": PAY_HERO_CALLBACK_URL
    }
    missing_vars = [key for key, value in required_vars.items() if not value]
    if missing_vars:
        error_msg = f"Missing required environment variables for payment service: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

validate_env_vars()

def get_humanization_cost(word_count: int, mode: str = 'standard') -> float:
    """
    Calculates the cost of a humanization task based on word count and mode.
    """
    if mode == 'essay':
        price = ESSAY_PRICE_PER_UNIT
    elif mode == 'document_formatter':
        price = FORMAT_ONLY_PRICE_PER_UNIT
    else: # 'standard'
        price = PRICE_PER_UNIT
    
    # Calculate cost based on word count blocks
    cost = (word_count / WORDS_PER_UNIT) * price
    return cost

def initiate_payhero_payment(amount: float, phone_number: str, external_reference: str, customer_name: str = "Customer") -> dict:
    """
    Initiates a payment request to the Pay Hero API.

    Args:
        amount (float): The amount to charge.
        phone_number (str): The customer's phone number.
        external_reference (str): A unique reference for the transaction.
        customer_name (str, optional): The customer's name. Defaults to "Customer".

    Returns:
        dict: The JSON response from the Pay Hero API.

    Raises:
        Exception: If the payment initiation fails.
    """
    payload = {
        "amount": amount,
        "phone_number": phone_number,
        "channel_id": int(PAY_HERO_CHANNEL_ID),
        "provider": "m-pesa",
        "external_reference": external_reference,
        "customer_name": customer_name,
        "callback_url": PAY_HERO_CALLBACK_URL
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {PAY_HERO_BASIC_AUTH_TOKEN}'
    }

    logger.info(f"Initiating payment of KES {amount} to {phone_number} with reference: {external_reference}")

    try:
        response = requests.post(PAY_HERO_API_URL, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        logger.info(f"Payment initiation successful for reference: {external_reference}")
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error during payment initiation for {external_reference}: {http_err} - {response.text}")
        raise Exception(f"Payment initiation failed with HTTP Error: {response.text}") from http_err
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error during payment initiation for {external_reference}: {req_err}")
        raise Exception(f"Payment initiation failed due to a request error: {req_err}") from req_err
