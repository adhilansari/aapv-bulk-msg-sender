import re
import logging
import phonenumbers
import pandas as pd

logger = logging.getLogger(__name__)

def validate_phone_numbers(phone_series, default_region='IN'):
    """Comprehensive phone number validation and normalization"""
    valid_numbers = []
    seen = set()
    
    if not isinstance(phone_series, pd.Series):
        raise ValueError("Input must be a pandas Series")
        
    for number in phone_series.dropna().astype(str):
        try:
            # Clean input
            cleaned = re.sub(r'[^\d+]', '', number).lstrip('0')
            if not cleaned:
                continue
                
            # Parse number
            parsed = phonenumbers.parse(cleaned, default_region)
            if not phonenumbers.is_valid_number(parsed):
                continue
                
            # Format without country code for WhatsApp Web
            formatted = phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.NATIONAL
            ).replace(' ', '').lstrip('0')
            
            # Add country code without +
            country_code = str(parsed.country_code)
            full_number = country_code + formatted
            
            if full_number not in seen:
                valid_numbers.append(full_number)
                seen.add(full_number)

        except Exception as e:
            logger.debug(f"Invalid number {number}: {str(e)}")
    
    logger.info(f"Validated {len(valid_numbers)} unique numbers from {len(phone_series)} inputs")
    return valid_numbers