# src/whatsapp_client.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import time
import random
import logging

class WhatsAppClient:
    def __init__(self):
        self.driver = None
        self.wait_timeout = 30
        self.chromedriver_path = r"assets\chromedriver.exe"  # Update path if needed
        
        # Configure logging
        logging.basicConfig(
            filename='whatsapp_client.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def initialize(self):
        """Initialize Chrome driver with anti-detection settings"""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("user-data-dir=./whatsapp_session")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            
            # Configure ChromeDriver service
            service = Service(
                executable_path=self.chromedriver_path,
                service_args=["--verbose", "--log-path=chromedriver.log"]
            )
            
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            self.driver.get("https://web.whatsapp.com/")
            logging.info("Initialized Chrome driver successfully")
            print("Scan QR code and press Enter when ready...")
            input()
            time.sleep(random.uniform(2, 4))  # Random wait after login
            return True
            
        except Exception as e:
            logging.error(f"Initialization failed: {str(e)}")
            raise

    def send_message(self, phone, message, attachment=None):
        """Send message with human-like interaction patterns"""
        try:
            self.driver.get(f"https://web.whatsapp.com/send?phone={phone}")
            self.wait_for_element('//div[@contenteditable="true"]', 45)
            
            # Human-like typing simulation
            input_box = self.driver.find_element(By.XPATH, '//div[@contenteditable="true"]')
            self.human_type(input_box, message)
            
            # Send message with random delay
            self.random_send()
            
            if attachment:
                self.send_attachment(attachment)
            
            logging.info(f"Message sent to {phone}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to send to {phone}: {str(e)}")
            return False

    def send_attachment(self, file_path):
        """Handle file attachments with error checking"""
        try:
            self.click_attachment_button()
            file_input = self.wait_for_element('//input[@accept="*"]', 10)
            file_input.send_keys(file_path)
            time.sleep(random.uniform(1, 2))
            self.random_send()
            logging.info(f"Attachment sent: {file_path}")
            return True
        except Exception as e:
            logging.error(f"Attachment failed: {str(e)}")
            return False

    def human_type(self, element, text):
        """Simulate human typing with random delays"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.08, 0.25))  # Natural typing speed

    def random_send(self):
        """Randomized send button click timing"""
        time.sleep(random.uniform(0.5, 1.5))
        self.driver.find_element(By.XPATH, '//span[@data-icon="send"]').click()
        time.sleep(random.uniform(1, 3))  # Wait after sending

    def wait_for_element(self, xpath, timeout=None):
        """Smart element waiting with dynamic timeout"""
        return WebDriverWait(self.driver, timeout or self.wait_timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

    def click_attachment_button(self):
        """Click attachment button with random delay"""
        time.sleep(random.uniform(0.3, 0.8))
        self.driver.find_element(By.XPATH, '//div[@title="Attach"]').click()

    def close(self):
        """Clean up resources safely"""
        if self.driver:
            try:
                self.driver.quit()
                logging.info("Browser closed successfully")
            except Exception as e:
                logging.error(f"Error closing browser: {str(e)}")