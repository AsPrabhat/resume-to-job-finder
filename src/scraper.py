from playwright.sync_api import sync_playwright
import time
import random

class LinkedInScraper:
    def scrape_jobs(self, role, k=5):
        # scrapes jobs from linkedin (backup method)
        print(f"Scraping {k} jobs for: {role}...")
        
        jobs = []
        
        with sync_playwright() as p:
            # Launch Brave Browser
            browser = p.chromium.launch(
                headless=False, 
                executable_path=r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                args=["--disable-gpu"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # URL encoding the role
            search_url = f"https://www.linkedin.com/jobs/search?keywords={role.replace(' ', '%20')}&location=India" # Change location if needed
            
            try:
                page.goto(search_url, timeout=60000)
                page.wait_for_selector(".jobs-search__results-list", timeout=10000)
                
                # Scroll to load more jobs if necessary
                for _ in range(3):
                    page.mouse.wheel(0, 1000)
                    time.sleep(1)

                # Extract job cards
                job_cards = page.locator("ul.jobs-search__results-list > li")
                count = job_cards.count()
                
                print(f"   Found {count} listings on page.")

                for i in range(min(count, k)):
                    card = job_cards.nth(i)
                    
                    try:
                        title = card.locator("h3.base-search-card__title").inner_text().strip()
                        company = card.locator("h4.base-search-card__subtitle").inner_text().strip()
                        link = card.locator("a.base-card__full-link").get_attribute("href")
                        
                        # We need description for matching. 
                        # In guest mode, this is tricky. We will grab the title/company for now
                        # and rely on title-semantic matching if description is hidden behind auth.
                        
                        jobs.append({
                            "title": title,
                            "company": company,
                            "link": link,
                            "search_role": role, # Tagging which role found this
                            "description": f"{title} at {company}" # Placeholder if full desc is blocked
                        })
                        
                    except Exception as e:
                        continue
                        
            except Exception as e:
                print(f"   Error scraping {role}: {e}")
            finally:
                browser.close()
                
        return jobs