import logging
import sqlite3
logging.basicConfig(level=logging.INFO)

def debug(message):
    logging.info(message)
    
conn = sqlite3.connect("data.db")
c = conn.cursor()

c.execute()