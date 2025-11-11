import json
import csv
import time
from pprint import pprint
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# --------------------------
# Helper Functions
# --------------------------
def safe_find_text(driver, by, selector):
    try:
        return driver.find_element(by, selector).text.strip()
    except:
        return ""

def safe_find_attr(driver, by, selector, attr):
    try:
        return driver.find_element(by, selector).get_attribute(attr)
    except:
        return ""

def extract_total_ratings(text):
    import re
    if not text:
        return "0"
    m = re.search(r'(\d+)', text)
    return m.group(1) if m else "0"

# --------------------------
# Setup Driver
# --------------------------
driver = webdriver.Chrome()
driver.maximize_window()

all_doctors_data = []

# --------------------------
# Loop through pages
# --------------------------
for page_num in range(1, 5):  # 1 to 250 pages
    print(f"\n🌍 Opening page {page_num} ...")
    url = f"https://doctor.webmd.com/providers/specialty/dermatology?pagenumber={page_num}"
    driver.get(url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, '//a[contains(@href, "doctor/") and contains(@class, "prov-name")]')
            )
        )
    except TimeoutException:
        print(f"⚠️ Timeout on page {page_num}, skipping...")
        continue

    # Collect doctor profile URLs
    doctor_links = [
        el.get_attribute("href")
        for el in driver.find_elements(By.XPATH, '//a[contains(@href, "doctor/") and contains(@class, "prov-name")]')
    ]

    print(f"✅ Total doctor links found on page {page_num}: {len(doctor_links)}")

    # --------------------------
    # Loop through each doctor link
    # --------------------------
    for doctor_profile in doctor_links [:5]:
        print(f"\n🎬 Scraping: {doctor_profile}")
        driver.get(doctor_profile)

        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'profile-topcard-wrap')]"))
            )
        except TimeoutException:
            print("⚠️ Doctor profile load timeout, skipping...")
            continue

        # Basic Info
        doctor_name = safe_find_text(driver, By.XPATH, "//h1[contains(@class, 'provider-full-name')]")
        image_url = safe_find_attr(driver, By.XPATH, "//img[contains(@class, 'loc-co-provim')]", "src")
        specialty = safe_find_text(driver, By.XPATH, '//span[contains(@class,"prov-specialty-name")]')
        average_rating = safe_find_text(driver, By.XPATH, '//span[contains(@class,"avg-ratings")]')
        mobile_no = safe_find_text(driver, By.XPATH, '//span[contains(@class, "svgicon-phone")]/following-sibling::span')

        # Total Ratings
        rating_text = safe_find_text(driver, By.CLASS_NAME, "loc-co-numrat")
        total_ratings = extract_total_ratings(rating_text)

        # First location Google Maps link
        first_location = safe_find_attr(driver, By.XPATH, '//div[contains(@class,"get-direction")]/a', 'href')

        # Reviews
        reviews_elements = driver.find_elements(By.XPATH, '//div[contains(@class,"provider-review")]')
        all_reviews = []
        for review in reviews_elements:
            rating = safe_find_attr(review, By.XPATH, './/div[contains(@class,"webmd-rate")]', 'aria-valuenow')
            comment = safe_find_text(review, By.XPATH, './/section[@class="reviewData"]/article')
            date = safe_find_text(review, By.XPATH, './/li[contains(@class,"reviewdate")]')
            all_reviews.append({"rating": rating, "comment": comment, "date": date})

        # Experience
        experience = safe_find_text(driver, By.XPATH, '//div[contains(@class,"years-of-exp")]')

        # Locations
        location_blocks = driver.find_elements(By.XPATH, "//div[contains(@class,'webmd-col') and contains(@class,'loc-')]")
        all_locations = []
        for block in location_blocks:
            try:
                clinic_name = block.find_element(By.XPATH, ".//div[contains(@class,'location-practice-name')]").text.strip()
            except:
                clinic_name = ""
            try:
                address = block.find_element(By.XPATH, ".//div[contains(@class,'location-address')]").text.strip()
            except:
                address = ""
            try:
                phone_number = block.find_element(By.XPATH, ".//a[contains(@class,'cta-phone')]").get_attribute("formattedphone")
            except:
                phone_number = ""
            full_address = f"{clinic_name} {address}".strip()
            if full_address:
                all_locations.append({"address": full_address, "phone": phone_number})

        # Biography
        biography = safe_find_text(driver, By.XPATH, "//div[contains(@class,'lhd-profile-bio')]")

        # Conditions & Procedures 
        condition_elements = driver.find_elements(
            By.XPATH, "//div[contains(@class,'common-condition-procedure-card') and contains(@data-card-icon,'conditions')]//ul//li//span"
        )
        conditions_treated = list(set([elem.text.strip() for elem in condition_elements if elem.text.strip()]))

        procedure_elements = driver.find_elements(
            By.XPATH, "//div[contains(@class,'common-condition-procedure-card') and contains(@data-card-icon,'procedures')]//ul//li//span"
        )
        procedures = list(set([elem.text.strip() for elem in procedure_elements if elem.text.strip()]))

        # Education & Certifications 
        result = {'Medical License': [], 'Certifications': [], 'Education & Training': []}
        subsections = driver.find_elements(By.CLASS_NAME, 'education-subsection')
        for subsection in subsections:
            header = safe_find_text(subsection, By.TAG_NAME, 'h2').upper()
            if "MEDICAL LICENSE" in header:
                wrappers = subsection.find_elements(By.CLASS_NAME, 'education-wrapper')
                for wrapper in wrappers:
                    school_div = wrapper.find_element(By.CLASS_NAME, 'school')
                    status_span = school_div.find_elements(By.CLASS_NAME, 'license-status')
                    status = status_span[0].text if status_span else ''
                    full_text = school_div.text
                    license_text = full_text.replace(status, '').strip(', ').strip()
                    result['Medical License'].append({'license': license_text, 'status': status})
            elif "CERTIFICATIONS" in header or "BOARD CERTIFICATIONS" in header:
                cert_wrappers = subsection.find_elements(By.CLASS_NAME, 'education-wrapper')
                for wrapper in cert_wrappers:
                    cert_name = safe_find_text(wrapper, By.CLASS_NAME, 'school')
                    if cert_name:
                        result['Certifications'].append(cert_name)
            elif "EDUCATION & TRAINING" in header:
                wrappers = subsection.find_elements(By.CLASS_NAME, 'education-wrapper')
                for wrapper in wrappers:
                    school_name = safe_find_text(wrapper, By.CLASS_NAME, 'school') or ""
                    year = safe_find_text(wrapper, By.CLASS_NAME, 'schoolyear') or ""
                    result['Education & Training'].append({'school': school_name, 'year': year})

        # Compile Doctor Data
        doctor_data = {
            "name": doctor_name,
            "biography": biography,
            "phone number": mobile_no,
            "profile link": doctor_profile,
            "Profile Image": image_url,
            "profession": specialty,
            "average_rating": average_rating,
            "experience": experience,
            "total_ratings": total_ratings,
            "conditions_treated": conditions_treated,
            "procedures_performed": procedures,
            "education_certifications": result,
            "locations": all_locations,
            "first_location_google_maps": first_location,
            "reviews": all_reviews,
        }

        pprint(doctor_data)
        all_doctors_data.append(doctor_data)

        print("✅ Doctor scraped successfully!")
        time.sleep(1.5)  # small delay between doctors

    print(f"✅ Page {page_num} completed successfully!\n")
    time.sleep(3)  # small delay between pages

# --------------------------
# Save to JSON & CSV
# --------------------------
driver.quit()



with open("doctors.json", "w", encoding="utf-8") as f:
    json.dump(all_doctors_data, f, indent=4, ensure_ascii=False)

print("✅ doctors.json file saved successfully!")

# 👇 Ab usi file ko read karke CSV create karo
with open("doctors.json", "r", encoding="utf-8") as f:
    all_doctors_data = json.load(f)

with open("doctors.csv", "w", newline='', encoding="utf-8") as f:
    writer = csv.writer(f)

    # CSV Header
    writer.writerow([
        "Doctor Name", "Profession", "Phone number", "Experience", "Average Rating", "Total Ratings",
        "Biography", "Profile Link", "Profile Image",
        "Conditions Treated", "Procedures Performed",
        "Education & Training", "Certifications", "Medical License",
        "Locations", "First Location (Google Maps)", "Total Reviews", "Sample Review"
    ])

    # Data rows
    for doctor in all_doctors_data:
        education = doctor.get("education_certifications", {})
        edu_train = "; ".join([
            f"{e.get('school', '')} ({e.get('year', '')})"
            for e in education.get("Education & Training", [])
        ])
        certs = ", ".join(education.get("Certifications", []))
        med_license = "; ".join([
            f"{m.get('license', '')} ({m.get('status', '')})"
            for m in education.get("Medical License", [])
        ])
        locations = "; ".join([loc.get("address", "") for loc in doctor.get("locations", [])])
        reviews = doctor.get("reviews", [])
        sample_review = "\n".join([r.get("comment", "").strip() for r in reviews])


        writer.writerow([
            doctor.get("name", ""),
            doctor.get("profession", ""),
            doctor.get("phone number", ""),
            doctor.get("experience", ""),
            doctor.get("average_rating", ""),
            doctor.get("total_ratings", ""),
            doctor.get("biography", ""),
            doctor.get("profile link", ""),
            doctor.get("Profile Image", ""),
            ", ".join(doctor.get("conditions_treated", [])),
            ", ".join(doctor.get("procedures_performed", [])),
            edu_train,
            certs,
            med_license,
            locations,
            doctor.get("first_location_google_maps", ""),
            len(reviews),
            sample_review
        ])

print("✅ doctors.csv file created successfully!")
