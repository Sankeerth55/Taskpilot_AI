from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        logs = []
        page.on("console", lambda msg: logs.append(f"{msg.type}: {msg.text}"))
        page.on("pageerror", lambda exc: logs.append(f"error: {exc}"))
        
        try:
            page.goto("http://localhost:3000", wait_until="networkidle", timeout=5000)
        except Exception as e:
            print(f"Navigation error: {e}")
            
        page.wait_for_timeout(3000)
        
        for log in logs:
            print(log)
            
        browser.close()

if __name__ == "__main__":
    run()
