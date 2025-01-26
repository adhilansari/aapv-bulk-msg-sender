import re
import logging
import phonenumbers

logger = logging.getLogger(__name__)

def validate_phone_numbers(phone_series, default_region='IN'):
    """Validate and normalize phone numbers"""
    valid_numbers = []
    seen = set()
    
    for number in phone_series:
        try:
            # Clean input
            cleaned = re.sub(r'\D', '', str(number))
            if len(cleaned) < 10:
                continue

            # Parse and validate
            parsed = phonenumbers.parse(cleaned, default_region)
            if not phonenumbers.is_valid_number(parsed):
                continue

            # Format to E.164
            formatted = phonenumbers.format_number(
                parsed, 
                phonenumbers.PhoneNumberFormat.E164
            )

            if formatted not in seen:
                valid_numbers.append(formatted)
                seen.add(formatted)

        except Exception as e:
            logger.warning(f"Invalid number {number}: {str(e)}")
    
    logger.info(f"Validated {len(valid_numbers)} numbers")
    return valid_numbers