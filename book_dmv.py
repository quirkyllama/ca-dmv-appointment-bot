import time
import argparse
import traceback
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from dmv_offices import ID_TO_OFFICE
# import config


parser = argparse.ArgumentParser()
parser.add_argument('--office_ids', help = "comma separated list of office codes")
parser.add_argument('--end_date', help = 'Last date (inclusive) to find appointments: YYYY-MM-DD')
parser.add_argument('--reason_realId', action='store_true')
parser.add_argument('--reason_register', action='store_true')
parser.add_argument('--full_name', type=str, required=True)
parser.add_argument('--dl_number', type=str, help="Driver's Licences (needed for some task types)", default=None)
parser.add_argument('--phone_number', type=str, help = "xxx-yyy-zzzz", required=True)
form_url = 'https://www.dmv.ca.gov/foa/clear.do?goTo=officeVisit&localeName=en'

args = parser.parse_args()
# tgt_date = datetime.strptime(config.TGT_DATE,'%B %d, %Y').date()

first_name, last_name = args.full_name.split()
phone = args.phone_number.split('-')
tgt_date = datetime.strptime(args.end_date,'%Y-%m-%d').date()
driver = webdriver.PhantomJS()

reasons = []
if args.reason_realId:
    reasons.append('taskRID')
if args.reason_register:
    reasons.append('taskVR')

class AppointmentBooked(Exception): pass

def look_for_appointments(office_id):
    office_name=ID_TO_OFFICE[office_id]
    try:
        driver.get(form_url)
        WebDriverWait(driver, 120).until(EC.presence_of_element_located((By.ID, "app_content")))

        # Enter form data
        office = Select(driver.find_element_by_name('officeId'))
        office.select_by_value(office_id)
        driver.find_element_by_id(len(reasons)).click()
        for reason in reasons:
            driver.find_element_by_id(reason).click()
            if reason == 'taskDL':
                driver.find_element_by_id('fdl_number').send_keys(args.dl_number)
        driver.find_element_by_id('first_name').send_keys(first_name)
        driver.find_element_by_id('last_name').send_keys(last_name)
        driver.find_element_by_name('telArea').send_keys(phone[0])
        driver.find_element_by_name('telPrefix').send_keys(phone[1])
        driver.find_element_by_name('telSuffix').send_keys(phone[2])
        driver.find_element_by_name('ApptForm').submit()

        WebDriverWait(driver, 120).until(EC.presence_of_element_located((By.ID, "ApptForm")))

        result_html = driver.page_source
        soup = BeautifulSoup(result_html, "html5lib")
        results = soup.findAll("td", {"data-title" : "Appointment"})

        # Get first Appointment result, which is the one for the selected location
        appt = results[0].find('strong')
        if appt is None:
            print("No appointment found")
            return
        appt_text = appt.get_text().strip()
        # Reformat date. Format returned is "Monday, August 21, 2017 at 10:00 AM'
        appt_date_time = datetime.strptime(appt_text,'%A, %B %d, %Y at %I:%M %p')
        # Remove the time, compare just the dates
        appt_date = appt_date_time.date()

        # Check if it matches the configured date.
        # Only true if the dates are the exact same, e.g. 2017-08-21 == 2017-08-21
        if appt_date < tgt_date:
            print("Congratulations! You've found a date on before your target date. Scheduling the appointment...")
            driver.find_element_by_id('ApptForm').submit()
            print("Confirming the appointment...")
            WebDriverWait(driver, 120).until(EC.presence_of_element_located((By.ID, "ApptForm")))
            driver.find_element_by_id('ApptForm').submit()
            print(f'Confirmed appointment for {appt_date_time} at {office_name}')
            driver.quit()
            raise AppointmentBooked
        else:
            print(f"The earliest appointment at {office_name} is {appt_date_time}")
            return True
    except Exception as e:
        traceback.print_stack()
        print(f"Error processineg {office_name}: ", e)
        return False
try:
    offices = [x.strip() for x in args.office_ids.split(",")]
    MIN_TIMEOUT=240
    timeout = MIN_TIMEOUT
    while True:
        for office in offices:
            if not look_for_appointments(office):
                timeout = timeout * 2
                print(f"Timeout now set to: {timeout} seconds")
            else:
                timeout = MIN_TIMEOUT
            time.sleep(MIN_TIMEOUT)
except AppointmentBooked:
    pass
    
