from dotenv import load_dotenv
import os
import time
import logging
import random
import sqlite3
from fastapi import FastAPI, HTTPException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# Load environment variables from .env if available
load_dotenv()

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def login_to_linkedIn(driver, username, password):
    logging.info("Navigating to LinkedIn login page")
    driver.get("https://www.linkedin.com/login")
    # Allow a brief delay for redirection if already logged in
    time.sleep(2)
    current_url = driver.current_url
    if "linkedin.com/feed" in current_url:
        logging.info(f"Already logged in. Current URL: {current_url}")
        return
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        logging.info("Login page loaded, proceeding with login.")
        
        driver.find_element(By.ID, "username").send_keys(username)
        driver.find_element(By.ID, "password").send_keys(password)
        
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input.search-global-typeahead__input"))
        )
        logging.info("Successfully logged in.")
    except Exception as e:
        logging.error(f"Error during LinkedIn login: {e}")
        raise HTTPException(status_code=500, detail="Login failed.")

def store_jobs_in_db(jobs):
    try:
        conn = sqlite3.connect("jobs.db")
        c = conn.cursor()
        # Create the table if it doesn't exist, with link as UNIQUE to avoid duplicates.
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                company TEXT,
                location TEXT,
                link TEXT UNIQUE
            )
        """)
        for job in jobs:
            try:
                c.execute(
                    "INSERT OR IGNORE INTO jobs (title, company, location, link) VALUES (?, ?, ?, ?)",
                    (job["title"], job["company"], job["location"], job["link"])
                )
            except Exception as e:
                logging.error(f"Database insertion error for job {job}: {e}")
        conn.commit()
    except Exception as db_e:
        logging.error(f"Error with database operations: {db_e}")
    finally:
        conn.close()
        logging.info("Database connection closed.")

def scrape_jobs_sync(query: str, location: str, max_pages: int = 5):
    jobs = []
    search_url = f"https://www.linkedin.com/jobs/search?keywords={query}&location={location}"
    logging.info(f"Navigating to: {search_url}")
    
    # Configure Selenium WebDriver with persistent profile and custom user-agent
    chrome_options = Options()
    chrome_options.add_argument("user-data-dir=D:\\MachineLearning\\TalentFlow\\backend\\chromeprofile")  # Update this path!
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36")
    # Uncomment for headless mode in production if desired:
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-webrtc")
    chrome_options.add_argument("--disable-software-rasterizer")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    # Remove webdriver flag to help hide automation
    driver.execute_cdp_cmd(
        'Page.addScriptToEvaluateOnNewDocument',
        {'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'}
    )
    
    try:
        # Retrieve LinkedIn credentials from environment variables
        username = os.environ.get("LINKEDIN_USERNAME")
        password = os.environ.get("LINKEDIN_PASSWORD")
        if not username or not password:
            logging.error("LinkedIn credentials not provided.")
            raise HTTPException(status_code=500, detail="LinkedIn credentials not provided.")
        
        login_to_linkedIn(driver, username, password)
        
        # Navigate to job search page
        driver.get(search_url)
        logging.debug("Navigated to job search page.")
        time.sleep(5)
        
        for page in range(max_pages):
            logging.info(f"--- Processing page {page + 1} ---")
            
            # Scroll down in a randomized, human-like fashion
            for i in range(5):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                delay = random.uniform(2, 3)
                logging.info(f"Page {page + 1}: Scrolled down {i + 1} times, waiting {delay:.2f} seconds")
                time.sleep(delay)
            
            try:
                container = WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "ul[class^='insiAph']"))
                )
                logging.info(f"Page {page + 1}: Job results container detected.")
            except Exception as te:
                logging.error(f"Page {page + 1}: Timeout waiting for job results container: {te}")
                break
            
            job_cards = container.find_elements(By.CSS_SELECTOR, "li[data-occludable-job-id]")
            logging.info(f"Page {page + 1}: Found {len(job_cards)} job cards")
            
            for index, card in enumerate(job_cards, start=1):
                logging.debug(f"Page {page + 1}: Processing job card {index}")
                title = "N/A"
                company = "N/A"
                location_text = "N/A"
                link = "N/A"
                
                try:
                    a_elem = card.find_element(By.CSS_SELECTOR, "a.job-card-list__title--link")
                    title = a_elem.text.strip()
                    link = a_elem.get_attribute("href")
                    logging.debug(f"Page {page + 1}, card {index}: Extracted title: {title}")
                    logging.debug(f"Page {page + 1}, card {index}: Extracted link: {link}")
                except Exception as e:
                    logging.error(f"Page {page + 1}, card {index}: Title/Link extraction error: {e}")
                
                try:
                    company_elem = card.find_element(By.CSS_SELECTOR, "div.artdeco-entity-lockup__subtitle")
                    company = company_elem.text.strip()
                    logging.debug(f"Page {page + 1}, card {index}: Extracted company: {company}")
                except Exception as e:
                    logging.error(f"Page {page + 1}, card {index}: Company extraction error: {e}")
                
                try:
                    location_elem = card.find_element(By.CSS_SELECTOR, "ul.job-card-container__metadata-wrapper li")
                    location_text = location_elem.text.strip()
                    logging.debug(f"Page {page + 1}, card {index}: Extracted location: {location_text}")
                except Exception as e:
                    logging.error(f"Page {page + 1}, card {index}: Location extraction error: {e}")
                    location_text = "N/A"
                
                if title != "N/A" or company != "N/A":
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": location_text,
                        "link": link
                    })
            
            # Attempt to click the "Next" button
            try:
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.jobs-search-pagination__button--next"))
                )
                logging.info(f"Page {page + 1}: Clicking 'Next' button")
                next_button.click()
                time.sleep(5)
            except Exception as e:
                logging.info(f"Page {page + 1}: 'Next' button not found or not clickable: {e}")
                break
                
    except Exception as e:
        logging.error(f"Error during scraping: {e}")
        raise HTTPException(status_code=500, detail="Error during scraping job postings.")
    finally:
        driver.quit()
        logging.info("Driver closed.")
    
    return jobs

@app.get("/scrape_jobs")
def scrape_jobs(query: str = "AI developer", location: str = "United States"):
    try:
        jobs = scrape_jobs_sync(query, location)
        # Store jobs in SQLite (ignores duplicates based on unique link)
        store_jobs_in_db(jobs)
        return {"query": query, "location": location, "jobs": jobs}
    except Exception as e:
        logging.error(f"Unhandled error: {e}")
        raise HTTPException(status_code=500, detail="Scraping failed.")
