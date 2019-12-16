import schedule
import time


schedule.every().day.at("00:00").do(job)

while True:
    schedule.run_pending()
    time.sleep(60)