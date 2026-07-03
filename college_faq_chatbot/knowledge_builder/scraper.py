"""
scraper.py - Scrape important pages from BVRIT Hyderabad website
"""

import requests
from bs4 import BeautifulSoup
import time
import os

BASE_URL = "https://bvrithyderabad.edu.in"

# Important pages discovered from the homepage
PAGES = {
    "About BVRIT Hyderabad": "https://bvrithyderabad.edu.in/about-bvrith/",
    "About Society – SVES": "https://bvrithyderabad.edu.in/sri-vishnu-educational-society/",
    "Vision & Mission": "https://bvrithyderabad.edu.in/about-bvrith/",
    "Management": "https://bvrithyderabad.edu.in/management/",
    "Principal": "https://bvrithyderabad.edu.in/principal/",
    "Organogram": "https://bvrithyderabad.edu.in/organogram/",
    "Admission Process": "https://bvrithyderabad.edu.in/admission/admission-process/",
    "EAMCET Ranks": "https://bvrithyderabad.edu.in/admission/eamcet-ranks/",
    "B-Category Admission": "https://bvrithyderabad.edu.in/admission/b-category/",
    "Fee Details": "https://bvrithyderabad.edu.in/admission/fee-details/",
    "Intake of Courses": "https://bvrithyderabad.edu.in/admission/intake-of-courses/",
    "Documents to Submit": "https://bvrithyderabad.edu.in/admission/documents-to-submit/",
    "Hostel Admission": "https://bvrithyderabad.edu.in/admission/hostel/",
    "Transportation": "https://bvrithyderabad.edu.in/admission/transportation/",
    "CSE Department": "https://bvrithyderabad.edu.in/computer-science-and-engineering/about-the-department/",
    "CSE (AI&ML) Department": "https://bvrithyderabad.edu.in/cse-artificial-intelligence-and-machine-learning/about-the-department/",
    "ECE Department": "https://bvrithyderabad.edu.in/electronics-and-communication-engineering/about-the-department/",
    "EEE Department": "https://bvrithyderabad.edu.in/electrical-and-electronics-engineering/about-the-department/",
    "IT Department": "https://bvrithyderabad.edu.in/information-technology/about-the-department/",
    "BS&H Department": "https://bvrithyderabad.edu.in/basic-sciences-and-humanities/about-the-department/",
    "Honor Degree Program": "https://bvrithyderabad.edu.in/honor-degree-program/",
    "Placements – Training & Placement Process": "https://bvrithyderabad.edu.in/placements/training-placement-process/",
    "Placements – Training & Placement Cell": "https://bvrithyderabad.edu.in/placements/training-and-placement-cell/",
    "Placements – Team": "https://bvrithyderabad.edu.in/placements/training-and-placement-team/",
    "Placements – Employability Skills": "https://bvrithyderabad.edu.in/placements/employability-skills/",
    "Placements – Internships": "https://bvrithyderabad.edu.in/placements/internships/",
    "Placements – Placement Details": "https://bvrithyderabad.edu.in/placements/placement-details/",
    "Placements – Testimonials": "https://bvrithyderabad.edu.in/placements/testimonials/",
    "Library": "https://bvrithyderabad.edu.in/library/",
    "Food and Cafetaria": "https://bvrithyderabad.edu.in/food-and-cafetaria/",
    "Gym": "https://bvrithyderabad.edu.in/gym/",
    "Temple": "https://bvrithyderabad.edu.in/temple/",
    "Security": "https://bvrithyderabad.edu.in/security/",
    "PCS Facilities": "https://bvrithyderabad.edu.in/pcs-facilities/",
    "Contact Us": "https://bvrithyderabad.edu.in/contact-us/",
    "Research & Development": "https://bvrithyderabad.edu.in/research/about-r-d/",
    "Faculty Thrust Areas": "https://bvrithyderabad.edu.in/research/faculty-domain-areas/",
    "Ph.D Awarded": "https://bvrithyderabad.edu.in/research/ph-d-awarded/",
    "Publications": "https://bvrithyderabad.edu.in/research/faculty-publications/",
    "Research Projects": "https://bvrithyderabad.edu.in/research/research-projects/",
    "Consultancy Projects": "https://bvrithyderabad.edu.in/research/consultancy-projects/",
    "Patents Published": "https://bvrithyderabad.edu.in/research/patents-filed/",
    "Patents Granted": "https://bvrithyderabad.edu.in/research/patents-granted/",
    "Center of Excellence (CoEs)": "https://bvrithyderabad.edu.in/research/coes/",
    "Alumni Speak": "https://bvrithyderabad.edu.in/alumni-speak/",
    "IKS and NEP": "https://bvrithyderabad.edu.in/iks-and-nep/",
    "NIRF": "https://bvrithyderabad.edu.in/nirf/",
    "PM Vidyalaxmi Scheme": "https://bvrithyderabad.edu.in/pm-vidyalaxmi-scheme/",
    "Entry – Exit System": "https://bvrithyderabad.edu.in/entry-exit-system/",
    "VSSC (Vishnu Student Success Center)": "https://bvrithyderabad.edu.in/differentiators/vssc/",
    "GSAC (Graduate Study Abroad Center)": "https://bvrithyderabad.edu.in/differentiators/gsac/",
    "IIC BVRITH": "https://bvrithyderabad.edu.in/differentiators/iic-bvrith/",
    "EDC (Entrepreneurship Development Cell)": "https://bvrithyderabad.edu.in/differentiators/entrepreneurship-development-cell-edc/",
    "Student Affairs Council (SAC)": "https://bvrithyderabad.edu.in/differentiators/student-affairs-council-sac/",
    "NSS Club": "https://bvrithyderabad.edu.in/student-activities/nss-club/",
    "Rotaract Club": "https://bvrithyderabad.edu.in/student-activities/rotaract-club/",
    "Sports Club": "https://bvrithyderabad.edu.in/student-activities/sports-club/",
    "CSI": "https://bvrithyderabad.edu.in/student-activities/csi/",
    "IEEE": "https://bvrithyderabad.edu.in/student-activities/ieee/",
    "ACM": "https://bvrithyderabad.edu.in/student-activities/acm/",
}


def scrape_page(url):
    """Scrape a URL and extract clean text."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        html = requests.get(url, headers=headers, timeout=15).text
        soup = BeautifulSoup(html, "lxml")
        
        # Remove unwanted elements
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        
        text = soup.get_text(separator="\n")
        
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if line:
                lines.append(line)
        
        return "\n".join(lines)
    except Exception as e:
        return f"Error scraping {url}: {e}"


def scrape_all_pages():
    """Scrape all important pages and return a dict of {title: text}."""
    results = {}
    os.makedirs("output", exist_ok=True)
    
    for title, url in PAGES.items():
        print(f"Scraping: {title} ... ", end="", flush=True)
        text = scrape_page(url)
        results[title] = text
        print(f"done ({len(text)} chars)")
        time.sleep(1)  # Be polite to the server
    
    return results


if __name__ == "__main__":
    data = scrape_all_pages()
    print(f"\nScraped {len(data)} pages successfully.")
