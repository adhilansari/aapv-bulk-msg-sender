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
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import (WebDriverException, 
                                      TimeoutException,
                                      NoSuchElementException)

class WhatsAppClient:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.driver = None
        self.wait = None
        self.session_id = uuid.uuid4().hex[:8]
        self.profile_path = os.path.abspath(f"./chrome_profiles/{self.session_id}")
        self._init_driver()
        self._handle_authentication()

    def _init_driver(self):
        """Initialize ChromeDriver with unique profile"""
        try:
            os.makedirs(self.profile_path, exist_ok=True)

            options = webdriver.ChromeOptions()
            options.add_argument(f"--user-data-dir={self.profile_path}")
            options.add_argument("--profile-directory=Default")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            
            service = Service(
                ChromeDriverManager().install(),
                service_args=['--verbose', '--log-path=./logs/chromedriver.log']
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
        """Handle WhatsApp authentication flow"""
        try:
            self.driver.get("https://web.whatsapp.com/")
            
            # Check for existing session first
            try:
                self.wait.until(EC.presence_of_element_located(
                    (By.XPATH, '//div[@aria-label="Chat list"]')
                ))
                self.logger.info("Using existing authenticated session")
                return
            except TimeoutException:
                pass

            qr_locator = (By.XPATH, '//canvas[@aria-label="Scan me!"]')
            qr_element = self.wait.until(EC.presence_of_element_located(qr_locator))
            self.logger.info("QR code detected - please scan within 2 minutes")
            
            # Wait for QR code to disappear
            self.wait.until(EC.invisibility_of_element(qr_element))
            self.logger.info("Authentication successful")

        except TimeoutException as e:
            self.logger.error("Authentication timeout")
            self._cleanup_resources()
            raise

    def send_message(self, phone: str, message: str, attachments: list = None) -> bool:
        """Send message with comprehensive error handling"""
        try:
            if not phone.startswith('+'):
                phone = f"+{phone.lstrip('00')}"
                
            self.driver.get(f"https://web.whatsapp.com/send?phone={phone}&text={message[:20]}")
            self._wait_for_interface()

            # Handle attachments first if present
            if attachments:
                return self._handle_attachments(attachments, message)
            
            # Text-only message
            if message:
                input_box = self.wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, '//div[@role="textbox"][@contenteditable="true"]')
                    )
                )
                input_box.send_keys(message)
                self._click_send_button()
                
            return True

        except Exception as e:
            self.logger.error(f"Failed to send to {phone}: {str(e)}")
            return False

    def _handle_attachments(self, file_paths: list, message: str = None) -> bool:
        """Process file attachments with captions"""
        try:
            # Click attach button
            attach_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, '//div[@title="Attach"]'))
            )
            self.driver.execute_script("arguments[0].click();", attach_button)
            
            # Upload files
            file_input = self.wait.until(
                EC.presence_of_element_located((By.XPATH, '//input[@type="file"]'))
            )
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Attachment not found: {file_path}")
                file_input.send_keys(os.path.abspath(file_path))
                time.sleep(1)  # Wait between uploads
                
            # Wait for preview to load
            self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, '//div[@data-testid="media-attachment-preview"]')
                )
            )
            
            # Add caption if provided
            if message:
                caption_input = self.wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, '//div[@role="textbox"][@contenteditable="true"]')
                    )
                )
                caption_input.send_keys(message)
                
            self._click_send_button()
            return True
            
        except Exception as e:
            self.logger.error(f"Attachment error: {str(e)}")
            return False

    def _click_send_button(self):
        """Enhanced send button click with multiple fallbacks"""
        try:
            send_btn = self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//button[.//span[@data-testid="send"]]')
                )
            )
            self.driver.execute_script("arguments[0].click();", send_btn)
            time.sleep(1)  # Wait for send animation
        except Exception:
            try:
                self.driver.execute_script(
                    'document.querySelector(\'button[aria-label*="Send"]\').click()'
                )
            except Exception as e:
                self.logger.error(f"Failed to click send button: {str(e)}")
                raise

    def _wait_for_interface(self):
        """Wait for message interface with error detection"""
        try:
            element = self.wait.until(
                EC.any_of(
                    EC.presence_of_element_located(
                        (By.XPATH, '//div[@role="textbox"][@contenteditable="true"]')
                    ),
                    EC.presence_of_element_located(
                        (By.XPATH, '//div[contains(text(), "Phone number invalid")]')
                    ),
                    EC.presence_of_element_located(
                        (By.XPATH, '//div[contains(text(), "not on WhatsApp")]')
                    )
                )
            )
            
            if any(err in element.text for err in ["invalid", "not on WhatsApp"]):
                raise ValueError(f"Invalid recipient: {element.text}")
                
        except TimeoutException:
            self.logger.error("Message interface timeout")
            raise

    def _cleanup_resources(self):
        """Thorough resource cleanup"""
        try:
            if self.driver:
                self.driver.quit()

            if os.path.exists(self.profile_path):
                os.system(f'rmdir /s /q "{self.profile_path}"')

            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'chrome' in proc.info['name'].lower() and self.session_id in ' '.join(proc.info['cmdline']):
                        proc.kill()
                    elif 'chromedriver' in proc.info['name'].lower():
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            self.logger.error(f"Cleanup error: {str(e)}")

    def __del__(self):
        self._cleanup_resources()