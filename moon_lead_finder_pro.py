# moon_lead_finder_pro.py — WITH EMAIL EXTRACTION

import os
import time
import re
import requests
import openai
import pandas as pd
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import streamlit as st

# Load .env keys
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- GPT Utility Functions ---
def expand_keywords(seed_keywords):
    prompt = f"Expand the following phrases into 10 short variations that suggest hiring or outsourcing for dev, AI, or tech services:\n{seed_keywords}"
    try:
        res = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip().split("\n")
    except:
        return [seed_keywords]

def get_page_title(url):
    try:
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.title.string.strip() if soup.title else ""
    except:
        return ""

# --- Email Extractor ---
def extract_email_from_url(url):
    try:
        r = requests.get(url, timeout=8)
        emails = set(re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", r.text))
        # Return most likely valid email (skip images, assets)
        for email in emails:
            if not any(x in email for x in ["png", "jpg", "css", "js", "svg"]):
                return email
        return "Not found"
    except:
        return "Error"

# --- GPT Intent & Pitch ---
def is_buying_intent_from_url(url, keyword):
    title = get_page_title(url)
    prompt = f"""A user searched: '{keyword}'\nURL: {url}\nPage title: '{title}'\n\nDoes this suggest someone is trying to hire for development, AI, or tech services? Reply: Yes or No."""
    try:
        r = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        return "yes" in r.choices[0].message.content.strip().lower()
    except:
        return False

def generate_pitch(keyword):
    prompt = f"""Write a short, helpful, and personalized outreach message to someone expressing this need: '{keyword}'.\nThe sender is Moon Technolabs — a dev and AI solutions company."""
    try:
        r = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return r.choices[0].message.content.strip()
    except:
        return ""

# --- Google Search (via SerpAPI) ---
def serpapi_search(query):
    try:
        url = "https://serpapi.com/search"
        params = {"q": query, "engine": "google", "api_key": SERPAPI_KEY, "num": 10}
        res = requests.get(url, params=params)
        data = res.json()
        return [r['link'] for r in data.get("organic_results", [])]
    except:
        return []

# --- Forum Scraping (basic HTML only) ---
def scrape_indiehackers():
    try:
        res = requests.get("https://www.indiehackers.com/forum")
        soup = BeautifulSoup(res.text, "html.parser")
        return ["https://www.indiehackers.com" + a['href'] for a in soup.select("a.thread-title") if a.get("href")]
    except:
        return []

def scrape_devto():
    try:
        res = requests.get("https://dev.to/t/discuss")
        soup = BeautifulSoup(res.text, "html.parser")
        return ["https://dev.to" + a['href'] for a in soup.select("a.crayons-story__hidden-navigation-link") if a.get("href")]
    except:
        return []

def scrape_reddit_custom_search(keyword):
    query = f"site:reddit.com {keyword}"
    return serpapi_search(query)

# --- Streamlit UI ---
st.set_page_config(page_title="Moon Technolabs: Lead Finder Pro", layout="wide")
st.title("🧠 Moon Technolabs — Lead Finder (with Email Extraction)")

with st.sidebar:
    st.header("⚙️ Settings")
    user_keywords = st.text_area("Seed Keywords", "hire AI developer\nneed app development")
    use_ai_variants = st.checkbox("🧠 Expand Keywords (GPT)", True)
    use_gpt_filter = st.checkbox("🎯 Filter Intent (GPT)", True)
    debug = st.checkbox("🐞 Debug Skips", False)
    run_search = st.button("🚀 Run Lead Finder")

if run_search:
    st.info("🔍 Searching and extracting emails...")
    base_keywords = [k.strip() for k in user_keywords.split("\n") if k.strip()]
    all_keywords = []

    if use_ai_variants:
        for base in base_keywords:
            st.write(f"🧠 Expanding: {base}")
            all_keywords.extend(expand_keywords(base))
    else:
        all_keywords = base_keywords

    sources = ["linkedin.com", "reddit.com", "quora.com", "stackoverflow.com"]
    leads = []

    for keyword in all_keywords:
        for site in sources:
            query = f'"{keyword}" site:{site}'
            results = serpapi_search(query)
            for link in results:
                if use_gpt_filter and not is_buying_intent_from_url(link, keyword):
                    if debug:
                        st.write(f"❌ Skipped: {link}")
                    continue
                email = extract_email_from_url(link)
                leads.append({
                    "Keyword": keyword,
                    "Source": site,
                    "URL": link,
                    "Email": email,
                    "Pitch": generate_pitch(keyword)
                })
            time.sleep(1.5)

    forum_links = scrape_indiehackers() + scrape_devto()
    for forum_url in forum_links[:15]:
        title = get_page_title(forum_url)
        if use_gpt_filter and not is_buying_intent_from_url(forum_url, title):
            if debug:
                st.write(f"❌ Skipped Forum: {forum_url}")
            continue
        email = extract_email_from_url(forum_url)
        leads.append({
            "Keyword": title,
            "Source": "Forum",
            "URL": forum_url,
            "Email": email,
            "Pitch": generate_pitch(title)
        })

    st.write("🔁 Reddit search...")
    for keyword in all_keywords:
        reddit_links = scrape_reddit_custom_search(keyword)
        for url in reddit_links:
            if use_gpt_filter and not is_buying_intent_from_url(url, keyword):
                if debug:
                    st.write(f"❌ Skipped Reddit: {url}")
                continue
            email = extract_email_from_url(url)
            leads.append({
                "Keyword": keyword,
                "Source": "Reddit",
                "URL": url,
                "Email": email,
                "Pitch": generate_pitch(keyword)
            })

    if leads:
        df = pd.DataFrame(leads)
        st.success(f"✅ Found {len(df)} leads!")
        st.dataframe(df)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Leads CSV", csv, "leads.csv", "text/csv")
    else:
        st.warning("No strong leads found. Try other keywords or disable GPT filter.")
