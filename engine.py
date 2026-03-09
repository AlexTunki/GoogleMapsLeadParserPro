import asyncio
import csv
import json
import logging
import math
import os
import random
import re
from datetime import datetime
from urllib.parse import quote, unquote_plus
from playwright.async_api import async_playwright, TimeoutError

def generate_grid(lat, lng, radius_km, step_km):
    grid = []
    lat_step = step_km / 111.0
    lng_step = step_km / (111.0 * math.cos(math.radians(lat)))
    steps = int(radius_km / step_km)
    
    for i in range(-steps, steps + 1):
        for j in range(-steps, steps + 1):
            if math.sqrt((i * step_km)**2 + (j * step_km)**2) <= radius_km:
                grid.append({
                    "lat": lat + (i * lat_step),
                    "lng": lng + (j * lng_step)
                })
    return grid

class ParserEngine:
    def __init__(self, ui_callback):
        self.ui_callback = ui_callback
        self.is_running = False
        self.is_paused = False
        self.skip_request = None # None, "NICHE", "CITY", "PROJECT"
        self.progress_file = "data/progress.json"
        self.log_file = "data/app_log.txt"
        self.progress_data = {}
        self.browser = None
        self.scraped_in_session = set()
        
        os.makedirs("data", exist_ok=True)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"\n--- New session {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        except: pass

    def log(self, message, color="white"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.ui_callback({"type": "LOG", "text": f"[{timestamp}] {message}", "color": color})
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except: pass
        
    def log_rejection(self, proj_name, city_name, niche, name, reason, url):
        filename = f"Rejects_{proj_name.replace(' ', '_')}.txt"
        try:
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{city_name} | {niche}] {name} - {reason} - {url}\n")
        except: pass

    def update_progress(self, info):
        self.ui_callback({"type": "PROGRESS", "info": info})

    async def sleep_with_checks(self, seconds):
        for _ in range(int(seconds * 10)):
            if not self.is_running: return False
            if self.skip_request: return False
            while self.is_paused and self.is_running:
                await asyncio.sleep(0.5)
            await asyncio.sleep(0.1)
        return True

    def load_progress(self, projects):
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    self.progress_data = json.load(f)
            except:
                self.progress_data = {}

        # Reset or Init Progress structure
        for proj in projects:
            p_key = f"proj_{proj['name']}"
            if p_key not in self.progress_data:
                self.progress_data[p_key] = {"completed": False, "collected": 0, "cities": {}}

            p_data = self.progress_data[p_key]
            for city_name in proj["cities"]:
                c_key = f"city_{city_name}"
                if c_key not in p_data["cities"]:
                    p_data["cities"][c_key] = {"completed": False, "niches": {}}
                
                c_data = p_data["cities"][c_key]
                for niche in proj["niches"]:
                    n_key = f"niche_{niche}"
                    if n_key not in c_data["niches"]:
                        c_data["niches"][n_key] = {"completed": False, "collected": 0, "grid_idx": 0}

    def save_progress(self):
        with open(self.progress_file, "w", encoding="utf-8") as f:
            json.dump(self.progress_data, f, ensure_ascii=False, indent=4)

    def reset_progress(self):
        self.progress_data = {}
        if os.path.exists(self.progress_file):
            try:
                os.remove(self.progress_file)
            except: pass

    async def get_city_coords(self, city_name):
        # We will look up from data/cities.json
        try:
            with open("data/cities.json", "r", encoding="utf-8") as f:
                cities_db = json.load(f)
                for c in cities_db:
                    if c["name"] == city_name:
                        return c["lat"], c["lng"]
        except: pass
        return 34.0522, -118.2437 # Default Fallback LA

    async def start(self, projects):
        self.is_running = True
        self.is_paused = False
        self.manual_stop = False
        self.skip_request = None
        self.scraped_in_session = set()
        
        self.load_progress(projects)
        
        self.log("🚀 Starting Google Maps parsing engine...", "#4CAF50")
        
        try:
            async with async_playwright() as p:
                self.browser = await p.chromium.launch(headless=False, args=['--start-maximized', '--disable-blink-features=AutomationControlled'])
                context = await self.browser.new_context(locale="en-US", permissions=["geolocation"])
                
                for proj in projects:
                    if not self.is_running: break
                    if self.skip_request == "PROJECT":
                        self.skip_request = None # Reset skip
                        
                    p_key = f"proj_{proj['name']}"
                    p_data = self.progress_data[p_key]
                    if p_data["completed"]: continue
                    
                    self.log(f"\n📂 PROJECT START: {proj['name']}", "#2196F3")
                    
                    target_quota = proj['quota']
                    
                    # Calculate sub-quotas
                    total_combinations = len(proj['cities']) * len(proj['niches'])
                    quota_per_combo = math.ceil(target_quota / total_combinations) if total_combinations > 0 else 0
                    
                    csv_filename = f"Leads_{proj['name'].replace(' ', '_')}.csv"
                    # Write CSV Headers if new
                    if not os.path.exists(csv_filename):
                        with open(csv_filename, mode='w', newline='', encoding='utf-8-sig') as file:
                            writer = csv.writer(file, delimiter=';')
                            writer.writerow(['Project', 'City', 'Niche', 'Company Name', 'Phone Number', 'Google Maps Link'])

                    for city_name in proj["cities"]:
                        if not self.is_running: break
                        if self.skip_request == "PROJECT": break
                        if self.skip_request == "CITY":
                            self.skip_request = None
                            
                        c_key = f"city_{city_name}"
                        c_data = p_data["cities"][c_key]
                        if c_data["completed"]: continue
                        
                        lat, lng = await self.get_city_coords(city_name)
                        grid_points = generate_grid(lat, lng, proj['radius'], proj['step'])

                        for niche in proj["niches"]:
                            if not self.is_running: break
                            if self.skip_request in ["PROJECT", "CITY"]: break
                            if self.skip_request == "NICHE":
                                self.skip_request = None
                                
                            n_key = f"niche_{niche}"
                            n_data = c_data["niches"][n_key]
                            if n_data["completed"]: continue
                            
                            combo_collected = n_data["collected"]
                            self.log(f"📍 Searching: {city_name} -> {niche}. (Collected {combo_collected}/{quota_per_combo})", "#FFC107")
                            
                            while n_data["grid_idx"] < len(grid_points):
                                if not self.is_running: break
                                if self.skip_request:
                                    if self.skip_request == "ZONE":
                                        n_data["grid_idx"] += 4
                                        self.skip_request = None
                                        self.log("⏭️ Manually skipped current and 3 next zones!", "orange")
                                        self.save_progress()
                                        continue
                                    elif self.skip_request == "NICHE":
                                        n_data["completed"] = True
                                        self.log(f"⏭️ Skipped Niche: {niche}", "orange")
                                    elif self.skip_request == "CITY":
                                        for nd in c_data["niches"].values(): nd["completed"] = True
                                        c_data["completed"] = True
                                        self.log(f"⏭️ Skipped City: {city_name}", "orange")
                                    elif self.skip_request == "PROJECT":
                                        for cd in p_data["cities"].values(): 
                                            cd["completed"] = True
                                            for nd in cd["niches"].values(): nd["completed"] = True
                                        p_data["completed"] = True
                                        self.log(f"⏭️ Skipped Project: {proj['name']}", "orange")
                                    self.save_progress()
                                    break
                                
                                # Check quota
                                if combo_collected >= quota_per_combo:
                                    self.log(f"✅ Quota of {quota_per_combo} businesses for {city_name}->{niche} completed!", "#4CAF50")
                                    n_data["completed"] = True
                                    self.save_progress()
                                    break
                                
                                point = grid_points[n_data["grid_idx"]]
                                query = f"{niche} near {point['lat']:.5f}, {point['lng']:.5f}"
                                
                                self.update_progress(f"Queue: {proj['name']} | {city_name} ({niche}) | Zone {n_data['grid_idx'] + 1}/{len(grid_points)}")
                                
                                # Process block
                                await context.set_geolocation({"longitude": point['lng'], "latitude": point['lat']})
                                collected_in_grid, unique_found = await self.process_grid(context, point, query, proj, city_name, niche, csv_filename, quota_per_combo - combo_collected)
                                
                                combo_collected += collected_in_grid
                                n_data["collected"] = combo_collected
                                p_data["collected"] += collected_in_grid
                                
                                mode = proj.get("mode", "Medium")
                                skip_steps = 1
                                
                                if mode == "Fast" and unique_found <= 2:
                                    skip_steps = 3
                                    self.log(f"⚡ Fast Mode: Found only {unique_found} new businesses. Skipping {skip_steps} zones ahead to save time.", "#FF9800")
                                elif mode == "Medium" and unique_found == 0:
                                    skip_steps = 2
                                    self.log(f"⚡ Medium Mode: Found 0 new businesses. Skipping 2 zones ahead.", "#FF9800")
                                
                                n_data["grid_idx"] += skip_steps
                                self.save_progress()
                                
                                if not await self.sleep_with_checks(1.5): break

                            if n_data["grid_idx"] >= len(grid_points):
                                n_data["completed"] = True
                                self.save_progress()
                                
                        # Check if all niches in city completed
                        if all(n["completed"] for n in c_data["niches"].values()):
                            c_data["completed"] = True
                            self.save_progress()

                    # Check overall project completion
                    if p_data["collected"] >= target_quota or all(c["completed"] for c in p_data["cities"].values()):
                        p_data["completed"] = True
                        self.log(f"🎉 Project {proj['name']} completely finished!", "#4CAF50")
                        self.save_progress()

        except Exception as e:
            self.log(f"Critical error: {str(e)}", "red")
        finally:
            self.is_running = False
            self.log("🛑 Engine stopped.", "white")
            
            if getattr(self, "manual_stop", False):
                self.reset_progress()
                self.log("🗑 Progress has been completely reset by User (Manual STOP).", "orange")
            else:
                # Check if EVERYTHING is completed naturally
                all_done = True
                for p_key in self.progress_data:
                    if not self.progress_data[p_key].get("completed", False):
                        all_done = False
                        break
                
                if all_done and len(self.progress_data) > 0:
                    self.reset_progress()
                    self.log("🎉 All tasks are fully completed! Progress file cleared.", "#4CAF50")

    async def process_grid(self, context, point, query, proj, city_name, niche, csv_filename, needed_amount):
        if needed_amount <= 0: return 0, 0
        
        collected = 0
        page = await context.new_page()
        
        url = f"https://www.google.com/maps/search/{quote(query)}/@{point['lat']},{point['lng']},14z/?hl=en"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            try:
                if await page.locator('button:has-text("Reject all")').is_visible(timeout=3000):
                    await page.click('button:has-text("Reject all")')
                elif await page.locator('button:has-text("Accept all")').is_visible(timeout=1000):
                    await page.click('button:has-text("Accept all")')
            except: pass
            
            await page.wait_for_selector('div[role="feed"]', timeout=10000)
        except Exception:
            try:
                await page.close()
            except: pass
            return 0, 0
        previously_counted = 0
        max_scrolls = 15
        for _ in range(max_scrolls):
            count = await page.locator('a[href^="https://www.google.com/maps/place/"]').count()
            if count == previously_counted:
                if not await self.sleep_with_checks(1): break
                if await page.locator('a[href^="https://www.google.com/maps/place/"]').count() == previously_counted:
                    break
            previously_counted = count
            await page.evaluate('''() => {
                const feed = document.querySelector('div[role="feed"]');
                if (feed) feed.scrollTo(0, feed.scrollHeight);
            }''')
            if not await self.sleep_with_checks(0.5): break

        count = await page.locator('a[href^="https://www.google.com/maps/place/"]').count()
        place_urls = []
        for i in range(count):
            try:
                href = await page.locator('a[href^="https://www.google.com/maps/place/"]').nth(i).get_attribute('href')
                if href and href not in place_urls:
                    place_urls.append(href)
            except: pass

        # Deduplicate place_urls based on company unique inner IDs
        unique_urls = []
        seen_ids = set()
        
        # Determine previous IDs from CSV if available to avoid scraping them again
        if os.path.exists(csv_filename):
            try:
                with open(csv_filename, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                    for listed_url in place_urls:
                        # Find the hex identifier 0x...:0x... which is unique to each place on maps
                        match = re.search(r'(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', listed_url)
                        uid = match.group(1) if match else listed_url
                        if uid in content or unquote_plus(listed_url).split('?')[0] in content:
                            seen_ids.add(uid)
            except: pass

        for href in place_urls:
            match = re.search(r'(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', href)
            uid = match.group(1) if match else href
            if uid not in seen_ids and uid not in self.scraped_in_session:
                seen_ids.add(uid)
                self.scraped_in_session.add(uid)
                unique_urls.append(href)

        self.log(f"Found {len(place_urls)} places. Filtering dupes... {len(unique_urls)} remaining in this zone.", "gray")

        async def process_place(url):
            if not self.is_running or self.skip_request: return None
            
            detail_page = await context.new_page()
            try:
                # Blocks heavy assets and map tiles to speed up 3x
                def intercept_route(route):
                    req_type = route.request.resource_type
                    url_req = route.request.url
                    # Google map tiles and streetview use /vt/ and /streetview/
                    if req_type in ["image", "media", "font", "stylesheet"] or "maps/vt/" in url_req or "streetview" in url_req or "log" in url_req:
                        return route.abort()
                    return route.continue_()
                
                await detail_page.route("**/*", intercept_route)
                # 'commit' guarantees it returns immediately as soon as network starts, preventing 20-second blocks
                try:
                    await detail_page.goto(url, timeout=10000, wait_until="commit")
                except:
                    pass # Continue even if timeout, page might still render
                
                # Wait for h1 to appear in DOM
                try:
                    await detail_page.wait_for_selector('h1', timeout=4000)
                    # wait an extra 0.5s for React to inject reviews and other buttons
                    await detail_page.evaluate("() => new Promise(r => setTimeout(r, 500))")
                except:
                    pass
                
                name_loc = detail_page.locator('h1')
                if not await name_loc.is_visible():
                    return None
                name = await name_loc.first.inner_text()
                
                has_web = await detail_page.locator('[data-item-id="authority"]').count() > 0
                if has_web:
                    self.log(f"🏢 Checking: {name[:30]}... ❌ (Has website -> skipped)", "#888888")
                    self.log_rejection(proj['name'], city_name, niche, name, "Has website", url)
                    return None
                
                # Check Reviews Filter if enabled
                filters = proj.get("filters", {})
                if filters.get("enabled", False):
                    # Robust Review Logic using JavaScript evaluation
                    try:
                        rev_text = await detail_page.evaluate('''() => {
                            let text = document.body.innerText;
                            let m = text.match(/([\\d,]+)\\s+reviews?/i);
                            if (m) return m[1];
                            let spanText = document.querySelector('.F7nice') ? document.querySelector('.F7nice').innerText : "";
                            let m2 = spanText.match(/\\(([\\d,]+)\\)/);
                            if (m2) return m2[1];
                            let reviewButton = Array.from(document.querySelectorAll('button')).find(b => b.innerText && b.innerText.toLowerCase().includes('reviews'));
                            if (reviewButton) {
                                let m3 = reviewButton.innerText.match(/([\\d,]+)/);
                                if (m3) return m3[1];
                            }
                            return "0";
                        }''')
                        rev_count = int(rev_text.replace(',', '').strip())
                    except:
                        rev_count = 0
                    
                    if rev_count < filters.get("min_rev", 0) or rev_count > filters.get("max_rev", 1000):
                        self.log(f"🏢 Checking: {name[:30]}... ❌ (Reviews: {rev_count} don't match filter)", "#888888")
                        self.log_rejection(proj['name'], city_name, niche, name, f"Reviews out of range ({rev_count})", url)
                        return None
                        
                    # Filter by Freshness    
                    freshness_opt = filters.get("freshness", "Any")
                    if freshness_opt != "Any" and rev_count > 0:
                        is_fresh = False
                        try:
                            def check_freshness_in_text(text, opt):
                                import re
                                text = text.lower()
                                # Strictly matches phrases like "3 days ago", "a month ago"
                                regex = r'\b(\d+|a|an|one|two|three)\s+(minute|min|hour|day|week|month)s?\s+ago\b'
                                matches = re.finditer(regex, text)
                                for m in matches:
                                    full_match = m.group(0)
                                    unit = m.group(2)
                                    
                                    is_hours = unit in ['minute', 'min', 'hour']
                                    is_days = unit == 'day'
                                    is_weeks = unit == 'week'
                                    is_months = unit == 'month'
                                    
                                    if opt == "24 hours":
                                        if is_hours or 'a day' in full_match or '1 day' in full_match: return True
                                    elif opt == "1 month":
                                        if is_hours or is_days or is_weeks or 'a month' in full_match or '1 month' in full_match: return True
                                    elif opt == "3 months":
                                        if is_hours or is_days or is_weeks or (is_months and any(x in full_match for x in ['a month', '1 month', '2 month', '3 month'])): return True
                                return False

                            # 1. Quick regex check on current page (Overview tab)
                            page_text = await detail_page.evaluate("() => document.body.innerText")
                            is_fresh = check_freshness_in_text(page_text, freshness_opt)
                            
                            if not is_fresh:
                                # 2. Fallback: Click Reviews tab, click Sort, click Newest
                                try:
                                    reviews_tab = detail_page.locator('button[role="tab"]:has-text("Reviews")')
                                    if await reviews_tab.count() > 0:
                                        await reviews_tab.first.click(timeout=2000, force=True)
                                        
                                        sort_btn = detail_page.locator('button[aria-label="Sort reviews"], button:has-text("Sort")')
                                        # Wait up to 2 seconds for sort button to appear
                                        await sort_btn.first.wait_for(state='visible', timeout=2000)
                                        await sort_btn.first.click(timeout=2000, force=True)
                                        
                                        newest_opt = detail_page.locator('div[role="menuitemradio"]:has-text("Newest")')
                                        await newest_opt.first.wait_for(state='visible', timeout=2000)
                                        await newest_opt.first.click(timeout=2000, force=True)
                                        
                                        # Wait for new reviews to load
                                        await detail_page.wait_for_timeout(1000)
                                        # Check again
                                        page_text = await detail_page.evaluate("() => document.body.innerText")
                                        is_fresh = check_freshness_in_text(page_text, freshness_opt)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                            
                        if not is_fresh:
                            self.log(f"🏢 Checking: {name[:30]}... ❌ (No fresh reviews for {freshness_opt})", "#888888")
                            self.log_rejection(proj['name'], city_name, niche, name, f"No fresh reviews ({freshness_opt})", url)
                            return None
                
                # Fetch Phone
                phone_loc = detail_page.locator('[data-item-id^="phone:tel:"]')
                phone = "Not specified"
                if await phone_loc.count() > 0:
                    phone = await phone_loc.first.inner_text()
                
                self.log(f"🟢 ADDED: {name[:25]}... | {city_name} | {niche}", "#00FF00")
                return [proj['name'], city_name, niche, name, phone, url]
                
            except Exception:
                return None
            finally:
                await detail_page.close()

        # Batch process URLs (up to 8 at a time to prevent CPU choke on Windows)
        batch_size = 8
        for i in range(0, len(unique_urls), batch_size):
            if not self.is_running or self.skip_request or collected >= needed_amount: break
            
            # Progress bar calculation
            current_progress = int((i / len(unique_urls)) * 100) if len(unique_urls) > 0 else 0
            self.ui_callback({"type": "BAR", "progress": current_progress, "text": f"Scraping: {city_name} -> {niche} | Checked {i}/{len(unique_urls)} in current Zone"})
            
            batch_urls = unique_urls[i:i+batch_size]
            tasks = [process_place(u) for u in batch_urls]
            results = await asyncio.gather(*tasks)
            
            for res in results:
                if res:
                    collected += 1
                    with open(csv_filename, mode='a', newline='', encoding='utf-8-sig') as file:
                        writer = csv.writer(file, delimiter=';')
                        writer.writerow(res)
                    if collected >= needed_amount:
                        break
                        
        try:
            await page.close()
        except: pass
                    
        return collected, len(unique_urls)