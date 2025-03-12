import sqlite3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def check_duplicates(db_path=r"D:\\MachineLearning\\TalentFlow\\backend\\jobs.db"):
    logger.info("Starting duplicate check process...")
    logger.info(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    logger.info("Checking if 'jobs' table exists in the database.")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs';")
    table = cursor.fetchone()
    if table is None:
        logger.warning("Table 'jobs' does not exist. Run the scraper first to create it.")
        conn.close()
        return
    
    logger.info("Table 'jobs' found. Querying for duplicates based on 'link' column.")
    cursor.execute("""
        SELECT link, COUNT(*) as cnt 
        FROM jobs 
        GROUP BY link 
        HAVING cnt > 1
    """)
    duplicates = cursor.fetchall()
    conn.close()
    
    if duplicates:
        logger.info("Duplicates found:")
        for link, count in duplicates:
            logger.info(f"Link: {link} appears {count} times")
    else:
        logger.info("No duplicates found.")

if __name__ == "__main__":
    check_duplicates()
