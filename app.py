from flask import Flask, request, render_template, jsonify
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote
import json
import pandas as pd

app = Flask(__name__)

CONTACT_KEYWORDS = ['contact', 'contact-us', 'contacts']
BLACKLIST_EMAILS = [
    "@godaddy", ", ", ".png", ".jpg", "@example", "domain", "jane.doe@", "jdoe@", "john.doe", 
    "first@", "last@", ".svg", ".webp", "sentry", "company", ".jped", "?", "%", "(", ")", "<", 
    ">", ";", ":", "[", "]", "{", "}", "\\", "|", '"', "'", "!", "#", "$", "^", "&", "*"
]

EMAIL_REGEX = re.compile(r'([a-zA-Z0-9._%+-]+@[a-zAZ0-9.-]+\.[a-zA-Z]{2,})')

SOCIAL_MEDIA_PATTERNS = {
    "instagram": r'https?://(?:www\.)?instagram\.com/@?[\w.-]+',
    "facebook": r'https?://(?:www\.)?facebook\.com/(?!tr\?id=)[\w.-]+',
    "youtube": r'https?://(?:www\.)?youtube\.com/(?:@[\w.-]+|channel/[\w-]+|user/[\w.-]+|c/[\w.-]+)', 
    "linkedin": r'https?://(?:www\.)?linkedin\.com/(?:in|company|edu|school)/[\w.-]+(?:\?[^\s]+)?',
    "twitter": r'https?://(?:www\.)?(?:twitter\.com|x\.com)/@?[\w.-]+',
    "tiktok": r'https?://(?:www\.)?tiktok\.com/@[\w.-]+'
}

BLACKLIST_SOCIAL_MEDIA = {
    "facebook": ['/plugins', '/embed', 'facebook.com/tr?id=', '/2008', '/business', '/people'],
    "instagram": ['/explore/', 'instagram.com/p/', 'instagram.com/stories/', 'instagram.com/accounts/'],
    "twitter": ['/search', 'twitter.com/explore', 'twitter.com/i/', '/intent'],
    "linkedin": ['/jobs'],
    "youtube": ['/shorts', '/music'],
    "tiktok": ['/video/', '/discover', 'tiktok.com/hashtag/']
}

def format_phone_number(phone):
    """Format phone numbers based on the given rules."""
    digits = re.sub(r'\D', '', phone)  # Remove all non-numeric characters
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]  # Remove leading '1'
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"  # Format as (000) 000-0000
    return phone  # Return the phone number as is if it doesn't meet the criteria

def extract_phone_from_soup(soup):
    """Extract phone numbers from any href="tel:..." and format them properly."""
    phone_links = set()

    for element in soup.find_all(href=True):
        href = element['href']
        if href.startswith("tel:"):
            phone = href[4:].strip()
            phone = unquote(phone).replace("%20", " ")  # Decode URL encoding & replace %20 with space
            formatted_phone = format_phone_number(phone)
            digits_only = re.sub(r'\D', '', formatted_phone)  # Remove all non-numeric characters
            if len(digits_only) >= 5:
                phone_links.add(formatted_phone)

    return phone_links

def extract_email_from_soup(soup):
    """Extract emails from mailto links and text using regex."""
    email_links = set()

    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith("mailto:"):
            email = href[7:].strip()
            if not any(black in email for black in BLACKLIST_EMAILS):
                email_links.add(email)

    text = soup.get_text(" ", strip=True)
    matches = EMAIL_REGEX.findall(text)
    for match in matches:
        if not any(black in match for black in BLACKLIST_EMAILS):
            email_links.add(match)

    return email_links

def extract_social_media_links(soup):
    """Extract social media links from the page."""
    social_media_links = {
        "instagram": set(),
        "facebook": set(),
        "youtube": set(),
        "linkedin": set(),
        "twitter": set(),
        "tiktok": set()
    }

    for platform, pattern in SOCIAL_MEDIA_PATTERNS.items():
        for match in re.findall(pattern, str(soup)):
            if any(black in match for black in BLACKLIST_SOCIAL_MEDIA.get(platform, [])):
                continue
            social_media_links[platform].add(match)

    return social_media_links

def extract_phone_and_email(url):
    print(f"Extracting phone and email from: {url}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.93 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return {"website": url, "phone": "", "email": "", "social_media": {}}

    page_source = response.text
    soup = BeautifulSoup(page_source, 'html.parser')

    phone_links = extract_phone_from_soup(soup)
    email_links = extract_email_from_soup(soup)
    social_media_links = extract_social_media_links(soup)

    extracted_data = {
        "website": url,
        "phone": ", ".join(sorted(phone_links)),
        "email": ", ".join(sorted(email_links)),
        "social_media": {platform: ", ".join(sorted(list(links))) for platform, links in social_media_links.items()}
    }

    return extracted_data

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract():
    url = request.json.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    data = extract_phone_and_email(url)
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
