import logging
import time
import json
import re
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta

class RedfinScraper:
    def __init__(self):
        # Initialize the scraper with logging and WebDriver setup
        self.driver = None
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        self.setup_driver()

    def setup_driver(self):
        try:
            # Configure Chrome options for headless automation
            chrome_options = Options()
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_argument(
                'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            # Setup WebDriver with ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # Bypass detection as an automated bot
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            self.logger.info("Selenium WebDriver setup completed successfully")
        except Exception as e:
            self.logger.error(f"Error setting up WebDriver: {str(e)}")
            raise

    def navigate_to_city(self, city: str, state: str) -> bool:
        try:
            # Navigate to the Redfin housing market homepage
            base_url = "https://www.redfin.com/us-housing-market"
            self.driver.get(base_url)
            time.sleep(3)

            # Locate the search box using its XPath
            search_box = WebDriverWait(self.driver, 10).until(
                ec.presence_of_element_located(
                    (By.XPATH, "/html/body/div[1]/div[6]/div[1]/div[2]/div/div[2]/div/div/div/form/div/div/input")
                )
            )

            # Type the query character by character with a delay to mimic human input
            for char in f"{city}, {state}":
                search_box.send_keys(char)
                time.sleep(random.uniform(0.1, 0.2))

            # Submit the search query
            time.sleep(2)
            search_box.send_keys(Keys.RETURN)
            time.sleep(5)

            return True

        except Exception as e:
            # Log any errors during navigation
            self.logger.error(f"Error in navigation: {str(e)}")
            return False

    def extract_price_data(self):
        try:
            self.logger.info("Parsing page content")
            price_data = {}

            # Extract the embedded JSON script containing price data
            content = self.driver.find_element(By.XPATH, "//body/div[1]/script[2]").get_attribute('innerHTML')

            # Define regex patterns for extracting data
            start_pattern = r'\{\\\"version\\\":\d+,\\\"errorMessage\\\":\\\"Success\\\",\\\"resultCode\\\":0,\\\"payload\\\":\{\\\"metrics\\\":\[\{\\\"label\\\":\\\"Median Sale Price\\\",\\\"value\\\":\\\"[^\\\"]+\\\",\\\"aggregateData\\\":'
            end_pattern = r',\{\\\"label\\\":\\\"# of Homes Sold\\\"'
            price_pattern = r'\{\\\"date\\\":\\\"([\d-]+)\\\",\\\"value\\\":\\\"(\d+)\\\",\\\"yoy\\\":\\\"([^\\\"]+)\\\"\}'

            # Locate the relevant section in the script
            start_match = re.search(start_pattern, content)
            if not start_match:
                self.logger.warning("Start pattern not found")
                return {}

            section_content = content[start_match.end():]

            # Extract the subsection containing the price data
            end_match = re.search(end_pattern, section_content)
            if not end_match:
                self.logger.warning("End pattern not found")
                return {}

            price_section = section_content[:end_match.start()]

            # Find all matches of price data
            matches = re.findall(price_pattern, price_section)
            if not matches:
                self.logger.warning("No price entries found")
                return {}

            self.logger.info(f"Found {len(matches)} price entries")

            # Store the extracted data in a dictionary
            for date, value, yoy in matches:
                price_data[date] = {
                    'price': int(value),
                    'year_over_year_change': yoy
                }

            return price_data

        except Exception as e:
            # Log errors during data extraction
            self.logger.error(f"Error in extract_price_data: {str(e)}")
            return {}

    def close(self):
        # Safely close the browser
        self.driver.quit()
        self.logger.info("Browser closed successfully")


def main():
    # Create an instance of the scraper
    scraper = RedfinScraper()
    try:
        # Prompt the user for input
        state = input("Enter state (e.g., TX): ")
        city = input("Enter city (e.g., Austin): ")

        # Navigate to the city page and extract price data
        if scraper.navigate_to_city(city, state):
            price_data = scraper.extract_price_data()
            if price_data:
                # Filter data from the last three years
                three_years_ago = (datetime.now() - timedelta(days=3 * 365)).strftime('%Y-%m')

                filtered_data = {
                    date: data
                    for date, data in price_data.items()
                    if date >= three_years_ago
                }
                sorted_data = dict(sorted(filtered_data.items(), reverse=True))

                # Display and save the results
                print("\nMedian Sale Price Data (Last 3 Years):")
                print(json.dumps(sorted_data, indent=2))
                print(f"\nTotal entries found: {len(sorted_data)}")

                filename = f"median_prices_{city.lower()}_{state.lower()}.json"
                with open(filename, 'w') as f:
                    json.dump(sorted_data, f, indent=2)
                print(f"\nResults saved to '{filename}'")
            else:
                print("No price data found")
        else:
            print("Failed to navigate to the city page")

    finally:
        # Ensure the browser is closed
        scraper.close()


if __name__ == "__main__":
    main()
