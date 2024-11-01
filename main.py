import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from openai import OpenAI
import os
from discord_webhook import DiscordWebhook

YOUR_DISCORD_WEBHOOK_URL = "your discord webhook url here"
YOUR_OPENAI_API_KEY = "your openai api key here"

# OpenAI Configuration
client = OpenAI(api_key=YOUR_OPENAI_API_KEY)

def setup_driver():
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode
    return webdriver.Chrome(service=service, options=options)

def scrape_hn_posts(driver, num_posts=5):
    driver.get('https://news.ycombinator.com/')
    posts = []
    current_posts = 0
    page = 1
    main_window = driver.current_window_handle

    while current_posts < num_posts:
        wait = WebDriverWait(driver, 10)
        
        try:
            # Wait for the story container to load
            story_containers = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "athing"))
            )
            
            for story in story_containers:
                if current_posts >= num_posts:
                    break
                
                try:
                    # Find title within the specific story container
                    title_element = story.find_element(By.CSS_SELECTOR, ".titleline > a:first-child")
                    title = title_element.text
                    link = title_element.get_attribute('href')
                    
                    # Skip if it's an internal link or job posting
                    if 'item?id=' in link or 'jobs' in link:
                        continue

                    try:
                        # Open link in new tab with error handling
                        driver.execute_script("window.open('');")
                        driver.switch_to.window(driver.window_handles[-1])
                        driver.get(link)
                        
                        # More generous wait time for content load
                        time.sleep(3)
                        
                        try:
                            content = driver.find_element(By.TAG_NAME, 'body').text[:500]
                        except:
                            content = "Could not extract content"
                            
                    except Exception as e:
                        content = "Failed to load external content"
                    finally:
                        # Always ensure we close the tab and return to main window
                        if len(driver.window_handles) > 1:
                            driver.close()
                        driver.switch_to.window(main_window)
                    
                    posts.append({
                        "title": title,
                        "link": link,
                        "content": content
                    })
                    current_posts += 1
                    
                except Exception as e:
                    print(f"Error processing story: {e}")
                    continue

            if current_posts < num_posts:
                page += 1
                driver.get(f'https://news.ycombinator.com/news?p={page}')
                time.sleep(1)  # Small delay between page loads
                
        except Exception as e:
            print(f"Error loading page {page}: {e}")
            break

    return posts

def analyze_with_openai(posts):
    prompt = "Analyze these Hacker News posts and provide a summary with key points and provided links for each:\n\n"
    for post in posts:
        prompt += f"Title: {post['title']}\nLink: {post['link']}\nContent Preview: {post['content']}\n\n"

    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an analyst summarizing Hacker News posts. For each post, provide a brief summary of the content and identify key points of interest."},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error analyzing posts with OpenAI: {e}"


def send_to_discord(content):
    try:
        webhook = DiscordWebhook(url=YOUR_DISCORD_WEBHOOK_URL, content=content)
        response = webhook.execute()
        if response.status_code == 204:  # Discord returns 204 on success
            print("Message sent successfully to Discord!")
        else:
            print(f"Failed to send message to Discord. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending message to Discord: {e}")


def main():
    driver = setup_driver()
    try:
        print("Scraping Hacker News posts...")
        posts = scrape_hn_posts(driver)
        
        print("Analyzing posts with OpenAI...")
        analysis = analyze_with_openai(posts)
        
        print("Sending to Discord...")
        send_to_discord(analysis)
        print("Done")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()

