import os
import time
import uuid
import logging
import psutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    NoSuchElementException,
)


class WhatsAppClient:
    def __init__(self, persistent_session=True):
        self.logger = logging.getLogger(__name__)
        self.driver = None
        self.wait = None
        self.session_id = "persistent" if persistent_session else uuid.uuid4().hex[:8]
        self.profile_path = os.path.abspath(f"./chrome_profiles/{self.session_id}")
        self.max_retries = 3
        self._init_driver()
        self._handle_authentication()

    def _capture_screenshot(self, name: str):
        """Capture debug screenshots"""
        path = f"./logs/{name}_{int(time.time())}.png"
        self.driver.save_screenshot(path)
        self.logger.info(f"Screenshot saved: {path}")

    def _cleanup_resources(self):
        """Thorough resource cleanup"""
        try:
            if self.driver:
                self.driver.quit()

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if "chrome" in proc.info[
                        "name"
                    ].lower() and self.session_id in " ".join(proc.info["cmdline"]):
                        proc.kill()
                    elif "chromedriver" in proc.info["name"].lower():
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            self.logger.error(f"Cleanup error: {str(e)}")

    def _init_driver(self):
        """Initialize ChromeDriver with enhanced options"""
        try:
            os.makedirs(self.profile_path, exist_ok=True)

            options = webdriver.ChromeOptions()
            options.add_argument(f"--user-data-dir={self.profile_path}")
            options.add_argument("--profile-directory=Default")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--remote-debugging-port=9222")
            options.add_argument("--disable-gpu")
            options.add_experimental_option(
                "excludeSwitches", ["enable-automation", "enable-logging"]
            )

            service = Service(
                ChromeDriverManager().install(),
                service_args=["--verbose", "--log-path=./logs/chromedriver.log"],
            )

            self.driver = webdriver.Chrome(service=service, options=options)
            self.wait = WebDriverWait(self.driver, 30)
            self.driver.set_page_load_timeout(45)
            self.logger.info(f"Driver initialized with session ID: {self.session_id}")

        except WebDriverException as e:
            self.logger.critical(f"Driver initialization failed: {str(e)}")
            self._cleanup_resources()
            raise

    def _handle_authentication(self):
        """Enhanced authentication flow with retries"""
        for attempt in range(self.max_retries):
            try:
                self.driver.get("https://web.whatsapp.com/")

                # Check for existing session
                try:
                    self.wait.until(
                        EC.presence_of_element_located(
                            (By.XPATH, '//div[@aria-label="Chat list"]')
                        )
                    )
                    self.logger.info("Using existing session")
                    return
                except TimeoutException:
                    self.logger.warning("No active session found")

                # QR Code handling
                qr_locator = (By.XPATH, '//canvas[contains(@aria-label, "Scan me")]')
                qr_element = self.wait.until(
                    EC.visibility_of_element_located(qr_locator)
                )
                self.logger.info("QR code detected - please scan")

                # Wait for QR scan
                self.wait.until(EC.invisibility_of_element(qr_element))
                self.logger.info("QR authentication successful")
                return

            except Exception as e:
                self.logger.error(f"Auth attempt {attempt+1} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    self._capture_screenshot("auth_failure")
                    raise RuntimeError("Authentication failed after multiple attempts")
                time.sleep(5)

    def send_message(self, phone: str, message: str, attachments: list = None) -> bool:
        """Robust message sending with error recovery"""
        try:
            phone = self._normalize_phone(phone)
            self.driver.get(f"https://web.whatsapp.com/send?phone={phone}")
            self._capture_screenshot(f"navigated_to_{phone}")  # Debug: After navigation

            # Validate chat window
            self._wait_for_chat_interface()
            self._capture_screenshot(
                f"chat_interface_loaded_{phone}"
            )  # Debug: After chat interface loads

            if attachments:
                return self._handle_attachments(attachments, message)

            if message:
                self._send_text_message(message)
                self._capture_screenshot(
                    f"message_typed_{phone}"
                )  # Debug: After typing message

            self._capture_screenshot(
                f"before_send_{phone}"
            )  # Debug: Before clicking send
            self._click_send_button()
            self._capture_screenshot(
                f"after_send_{phone}"
            )  # Debug: After clicking send

            return True

        except Exception as e:
            self.logger.error(f"Message failed: {str(e)}")
            self._capture_screenshot(f"send_error_{phone}")
            return False

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number format"""
        if not phone.startswith("+"):
            phone = f"+{phone.lstrip('00')}"
        return phone

    def _wait_for_chat_interface(self):
        """Wait for chat elements to load"""
        try:
            # Wait for the chat panel to load
            self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, '//div[@data-testid="conversation-panel-body"]')
                )
            )

            # Wait for the input box to be clickable
            self.wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        '//div[@contenteditable="true"][@data-testid="conversation-compose-box-input"]',
                    )
                )
            )

            # Additional check for the send button
            self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, '//button[@aria-label="Send"]')
                )
            )

            # Small delay to ensure everything is ready
            time.sleep(2)  # Increase delay if needed
        except TimeoutException:
            self.logger.error("Chat interface failed to load")
            self._capture_screenshot("chat_interface_timeout")
            raise

    def _send_text_message(self, message: str):
        """Send text message with chunking"""
        try:
            input_box = self.wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        '//div[@contenteditable="true"][@data-testid="conversation-compose-box-input"]',
                    )
                )
            )
            input_box.clear()
            time.sleep(1)  # Delay after clearing the input box

            # Split and send message in chunks
            chunks = [message[i : i + 2000] for i in range(0, len(message), 2000)]
            for chunk in chunks:
                input_box.send_keys(chunk)
                time.sleep(0.5)  # Delay between chunks

            self._click_send_button()
        except Exception as e:
            self.logger.error(f"Failed to send text message: {str(e)}")
            self._capture_screenshot("send_text_error")
            raise

    def _click_send_button(self):
        """Multiple strategies for sending messages"""
        try:
            # Wait for the send button to be clickable
            send_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Send"]'))
            )

            # Scroll the button into view (if needed)
            self.driver.execute_script("arguments[0].scrollIntoView(true);", send_btn)
            time.sleep(1)  # Delay after scrolling

            # Click the button using JavaScript
            self.driver.execute_script("arguments[0].click();", send_btn)
            time.sleep(2)  # Delay after clicking the send button
        except Exception as e:
            self.logger.error(f"Failed to click send button: {str(e)}")
            self._capture_screenshot("send_button_error")
            raise

    def __del__(self):
        self._cleanup_resources()
