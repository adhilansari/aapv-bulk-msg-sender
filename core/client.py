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
from selenium.common.exceptions import WebDriverException, TimeoutException

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
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--remote-debugging-port=0")
            options.add_argument("--start-maximized")
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            
            service = Service(
                ChromeDriverManager().install(),
                service_args=['--verbose']
            )

            self.driver = webdriver.Chrome(service=service, options=options)
            self.wait = WebDriverWait(self.driver, 30)
            time.sleep(2)  # Initialization delay
            self.logger.info(f"Driver initialized with session ID: {self.session_id}")

        except WebDriverException as e:
            self.logger.critical(f"Driver initialization failed: {str(e)}")
            self._cleanup_resources()
            raise

    def _handle_authentication(self):
        """Handle WhatsApp authentication flow"""
        try:
            self.driver.get("https://web.whatsapp.com/")
            
            qr_locator = (By.XPATH, '//canvas[@aria-label="Scan me!"]')
            chat_locator = (By.XPATH, '//div[@role="textbox"]')
            
            element = self.wait.until(
                EC.any_of(
                    EC.presence_of_element_located(qr_locator),
                    EC.presence_of_element_located(chat_locator)
                )
            )
            
            if "canvas" in element.tag_name:
                self.logger.info("QR code detected - please scan within 2 minutes")
                self.wait.until_not(EC.presence_of_element_located(qr_locator))
                self.logger.info("Authentication successful")

        except TimeoutException as e:
            self.logger.error("Authentication timeout")
            self._cleanup_resources()
            raise

    def send_message(self, phone: str, message: str, attachments: list = None) -> bool:
        """Send message with error handling"""
        try:
            self.driver.get(f"https://web.whatsapp.com/send?phone={phone}")
            self._wait_for_interface()

            if message:
                input_box = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]'))
                )
                input_box.send_keys(message)

            if attachments:
                self._handle_attachments(attachments)

            self._click_send_button()
            time.sleep(2)
            return True

        except Exception as e:
            self.logger.error(f"Failed to send to {phone}: {str(e)}")
            return False

    def _cleanup_resources(self):
        """Clean up all browser resources"""
        try:
            if self.driver:
                self.driver.quit()

            # Cleanup profile directory
            if os.path.exists(self.profile_path):
                os.system(f'rmdir /s /q "{self.profile_path}"')

            # Kill related processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'chrome' in proc.info['name'].lower():
                        if self.session_id in ' '.join(proc.info['cmdline']):
                            proc.kill()
                    elif 'chromedriver' in proc.info['name'].lower():
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            self.logger.error(f"Cleanup error: {str(e)}")

    def _wait_for_message_interface(self):
        """Wait for message composition interface to load"""
        self.wait.until(
            EC.presence_of_element_located((By.XPATH, '//div[@role="textbox"]'))
        )

    def _click_send_button(self):
        """Click send button with multiple fallback strategies"""
        try:
            self.wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Send"]'))
            ).click()
        except:
            # Fallback to JavaScript click
            self.driver.execute_script("document.querySelector('button[aria-label=\"Send\"]').click()")

    def _handle_attachments(self, file_paths: list):
        """Process file attachments"""
        try:
            self.wait.until(
                EC.element_to_be_clickable((By.XPATH, '//div[@title="Attach"]'))
            ).click()
            
            for file_path in file_paths:
                file_input = self.driver.find_element(
                    By.XPATH, '//input[@type="file"]'
                )
                file_input.send_keys(os.path.abspath(file_path))
                time.sleep(1)  # Wait between attachments
            
            self._click_send_button()

        except Exception as e:
            raise RuntimeError(f"Attachment failed: {str(e)}")


    def __del__(self):
        self._cleanup_resources()