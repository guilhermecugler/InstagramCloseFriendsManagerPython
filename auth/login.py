# Author: Guilherme Cugler
# GitHub: guilhermecugler
# Email: guilhermecugler@gmail.com
# Contact: +5513997230761 (WhatsApp)

from ast import Await
import asyncio
import json
import os
from tkinter import messagebox
from warnings import catch_warnings
from playwright.async_api import async_playwright
from processing.processor import load_processed_ids
import logging

def run_async_login(username, password, app, two_factor):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_login(username, password, app, two_factor))
    loop.close()

async def async_login(username, password, app, two_factor):
    app.update_status("Logging in...")
    app.log("Starting login process...")
    logging.info("Starting login process for user: %s", username)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto("https://www.instagram.com/accounts/login/?hl=en-us%3Fnext%3Dhttps%3A%2F%2Fwww.instagram.com%2Faccounts%2Fclose_friends%2F%3Fhl%3Den-us%26__coig_login%3D1#")
            await page.fill("input[name='username']", username)
            await page.fill("input[name='password']", password)
            await page.click("button[type='submit']")

            if two_factor:
                app.log("Waiting for two-factor authentication...")
                await page.wait_for_timeout(60000)  # Aguarda 1 minuto para a autenticação de dois fatores

            try:
                save_info_button = page.locator("//button[text()='Save info']")
                await save_info_button.wait_for(state="visible", timeout=20000)
                if save_info_button.is_visible():
                    await save_info_button.click()
            except Exception as e:
                pass
                
            await page.goto("https://www.instagram.com/accounts/close_friends/?hl=en-us&__coig_login=1")
            # await page.wait_for_load_state("networkidle")

            close_friends_title = page.locator("//h2[text()='Close friends']")
            await close_friends_title.wait_for(state="visible", timeout=15000)

            if not close_friends_title.is_visible():
                app.log("Login failed: Invalid credentials")
                messagebox.showerror("Error", "Login failed! Check your credentials")
                await browser.close()
                return
            await context.storage_state(path="state.json")
            app.log("Session state saved successfully")
            logging.info("Session state saved successfully for user: %s", username)

            cookies = await context.cookies()
            sessionid = next(c['value'] for c in cookies if c['name'] == 'sessionid')
            csrftoken = next(c['value'] for c in cookies if c['name'] == 'csrftoken')

            user_id = await page.evaluate(f'''
                (async () => {{
                    const response = await fetch(`https://www.instagram.com/web/search/topsearch/?query={username}`);
                    const data = await response.json();
                    return data.users.find(u => u.user.username === "{username}").user.pk;
                }})();
            ''')

            app.current_user = username
            app.loaded_session = {
                "user_id": user_id,
                "cookies": {
                    "sessionid": sessionid,
                    "csrftoken": csrftoken
                }
            }

            save_session(app)
            app.load_sessions()
            app.processed_ids = load_processed_ids(app.current_user)

            app.log(f"Login successful! User ID: {user_id}")
            logging.info("Login successful for user: %s, User ID: %s", username, user_id)

            await browser.close()

    except Exception as e:
        app.log(f"Error during login: {str(e)}")
        logging.error("Error during login for user: %s, Error: %s", username, str(e))
        messagebox.showerror("Error", f"Login failed: {str(e)}")

def save_session(app):
    if not app.current_user:
        return

    session_dir = "sessions"
    if not os.path.exists(session_dir):
        os.makedirs(session_dir)

    try:
        session_data = {
            "user_id": app.loaded_session["user_id"],
            "cookies": app.loaded_session["cookies"]
        }

        with open(f"{session_dir}/{app.current_user}_session.json", "w") as f:
            json.dump(session_data, f, indent=4)

        app.log(f"Session saved for {app.current_user}")
        logging.info("Session saved for user: %s", app.current_user)
    except Exception as e:
        app.log(f"Error saving session: {str(e)})")
        logging.error("Error saving session for user: %s, Error: %s", app.current_user, str(e))
