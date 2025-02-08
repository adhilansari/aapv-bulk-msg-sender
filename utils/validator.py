import os
import re
import logging
import phonenumbers
import pandas as pd

logger = logging.getLogger(__name__)


def validate_phone_numbers(phone_series, default_country_code="+91"):
    """Comprehensive phone validation with default country code"""
    valid = []
    seen = set()

    for num in pd.Series(phone_series).dropna().astype(str):
        try:
            # Clean input
            num = re.sub(r"[^\d+]", "", num).lstrip("0")
            if not num:
                continue

            # Add default country code if not present
            if not num.startswith("+"):
                num = f"{default_country_code}{num}"

            parsed = phonenumbers.parse(num, None)
            if not (
                phonenumbers.is_valid_number(parsed)
                and phonenumbers.is_possible_number(parsed)
            ):
                continue

            formatted = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )

            if formatted not in seen:
                valid.append(formatted)
                seen.add(formatted)

        except Exception as e:
            logger.debug(f"Invalid number {num}: {str(e)}")

    logger.info(f"Validated {len(valid)} numbers")
    return valid


def validate_message(message: str):
    """Message content validation"""
    if len(message) > 40000:
        raise ValueError("Message exceeds 40,000 character limit")
    return True


def validate_attachments(file_paths: list):
    """Attachment validation"""
    if len(file_paths) > 10:
        raise ValueError("Maximum 10 attachments allowed")

    for path in file_paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        if os.path.getsize(path) > 100 * 1024 * 1024:  # 100MB
            raise ValueError(f"File too large: {os.path.basename(path)}")
    return True
