from playwright.sync_api import sync_playwright, expect

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # 1. Navigate to the home page
            page.goto("http://localhost:8000/", timeout=10000)

            # 2. Assert: Check for a key element on the home page
            # This confirms the page has loaded correctly.
            heading = page.get_by_role("heading", name="Welcome to eSchool")
            expect(heading).to_be_visible()

            # 3. Screenshot: Capture the final result for visual verification.
            screenshot_path = "jules-scratch/verification/verification.png"
            page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()
