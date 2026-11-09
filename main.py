import os
import zipfile
import json
import uuid
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
from telethon.errors import (
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
    UserDeactivatedError,
    UserDeactivatedBanError,
    AuthKeyUnregisteredError
)

# API Credentials
API_ID = 32806977
API_HASH = "c31b980939409476c8531b20c10a9b7a"
BOT_TOKEN = "8909078160:AAFZaQBDQpf3_Dnl87PMbq9w27Egy_9bWQ8"

# ----------------- ADMIN & KEY CONFIG -----------------
ADMIN_ID = 5143571839  # ⚠️ এখানে তোমার নিজের Telegram User ID বসাও!
KEYS_FILE = "keys.json"
USERS_FILE = "active_users.json"

bot = TelegramClient("SessionBot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_sessions = {}

# General User Keyboard
MAIN_KEYBOARD = [
    [Button.text("➕ Create Session", resize=True), Button.text("📩 Read OTP", resize=True)],
    [Button.text("🔍 Check Session", resize=True), Button.text("🚫 Check Spam", resize=True)],
    [Button.text("✂️ Split Sessions", resize=True), Button.text("🧩 Merge Sessions", resize=True)]
]

# Admin Keyboard (With Quick Key Generation Buttons)
ADMIN_KEYBOARD = [
    [Button.text("🔑 Gen 1 Day", resize=True), Button.text("🔑 Gen 7 Days", resize=True), Button.text("🔑 Gen 30 Days", resize=True)],
    [Button.text("➕ Create Session", resize=True), Button.text("📩 Read OTP", resize=True)],
    [Button.text("🔍 Check Session", resize=True), Button.text("🚫 Check Spam", resize=True)],
    [Button.text("✂️ Split Sessions", resize=True), Button.text("🧩 Merge Sessions", resize=True)]
]

# ----------------- DATA HELPERS -----------------
def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)

def is_user_active(chat_id):
    if chat_id == ADMIN_ID:
        return True
    active_users = load_json(USERS_FILE)
    user_data = active_users.get(str(chat_id))
    if not user_data:
        return False
    
    expiry_time = datetime.fromisoformat(user_data["expiry"])
    if datetime.now() > expiry_time:
        del active_users[str(chat_id)]
        save_json(USERS_FILE, active_users)
        return False
    return True

def clean_file(file_path):
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

def extract_session_files(download_path):
    extracted_sessions = []
    if download_path.endswith(".zip"):
        extract_dir = f"temp_zip_{int(datetime.now().timestamp())}"
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(download_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        for root, _, files in os.walk(extract_dir):
            for f in files:
                if f.endswith(".session"):
                    extracted_sessions.append(os.path.join(root, f))
    elif download_path.endswith(".session"):
        extracted_sessions.append(download_path)
    return extracted_sessions

def generate_key_action(days):
    new_key = f"KEY-{days}D-" + str(uuid.uuid4())[:8].upper()
    keys = load_json(KEYS_FILE)
    keys[new_key] = {"days": days}
    save_json(KEYS_FILE, keys)
    return new_key

# ----------------- KEY MANAGEMENT HANDLERS -----------------

@bot.on(events.NewMessage(pattern=r"/genkey (?P<duration>\d+d)"))
async def genkey_cmd_handler(event):
    if event.chat_id != ADMIN_ID:
        return
    duration_str = event.pattern_match.group("duration")
    days = int(duration_str.replace("d", ""))
    new_key = generate_key_action(days)
    await event.respond(f"🔑 **New Key Generated!**\n\n🎟️ **Key:** `{new_key}`\n⏳ **Duration:** `{days}` Days")

@bot.on(events.NewMessage(pattern=r"/redeem (?P<key>\S+)"))
async def redeem_handler(event):
    chat_id = str(event.chat_id)
    key_input = event.pattern_match.group("key").strip()
    keys = load_json(KEYS_FILE)

    if key_input not in keys:
        await event.respond("❌ **Invalid or Expired Key!** Please check and try again.")
        return

    days = keys[key_input]["days"]
    expiry_date = datetime.now() + timedelta(days=days)

    active_users = load_json(USERS_FILE)
    active_users[chat_id] = {"expiry": expiry_date.isoformat()}
    save_json(USERS_FILE, active_users)

    del keys[key_input]
    save_json(KEYS_FILE, keys)

    kb = ADMIN_KEYBOARD if event.chat_id == ADMIN_ID else MAIN_KEYBOARD
    await event.respond(
        f"🎉 **Key Activated Successfully!**\n\n"
        f"⏳ Subscription Valid Until: `{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"You can now use all bot features!",
        buttons=kb
    )

# ----------------- START & CANCEL HANDLERS -----------------

@bot.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    chat_id = event.chat_id

    if not is_user_active(chat_id):
        await event.respond(
            "⚠️ **Access Denied!**\n\n"
            "TO Get Key\n"
            "dm : - @Cringe7x\n\n"
            "🔑 Activate Key Using: `/redeem YOUR_KEY`"
        )
        return

    user_sessions[chat_id] = {
        "numbers": [],
        "current_index": 0,
        "client": None,
        "phone": None,
        "phone_code_hash": None,
        "generated_files": [],
        "state": "IDLE"
    }

    kb = ADMIN_KEYBOARD if chat_id == ADMIN_ID else MAIN_KEYBOARD
    await event.respond(
        "👋 **Welcome to Multi-Utility Session Bot!**\n\n"
        "Buttons menu is active at the bottom. Choose an option to start:",
        buttons=kb
    )

@bot.on(events.NewMessage(pattern="/cancel"))
async def cancel_handler(event):
    chat_id = event.chat_id
    if not is_user_active(chat_id):
        return

    kb = ADMIN_KEYBOARD if chat_id == ADMIN_ID else MAIN_KEYBOARD
    if chat_id in user_sessions:
        data = user_sessions[chat_id]
        if data.get("client"):
            try:
                await data["client"].disconnect()
            except Exception:
                pass
        for file_path in data.get("generated_files", []):
            clean_file(file_path)
        del user_sessions[chat_id]
        await event.respond("❌ Process cancelled successfully.", buttons=kb)
    else:
        await event.respond("No active process. Choose an option from below:", buttons=kb)

async def process_next_number(event, chat_id):
    data = user_sessions[chat_id]
    kb = ADMIN_KEYBOARD if chat_id == ADMIN_ID else MAIN_KEYBOARD
    
    if data["current_index"] >= len(data["numbers"]):
        total_success = len(data["generated_files"])
        if total_success == 0:
            await event.respond("⚠️ No accounts were logged in successfully.", buttons=kb)
            del user_sessions[chat_id]
            return

        data["state"] = "AWAITING_EXPORT_CHOICE"
        buttons = [
            [Button.inline("📁 Send as .session files", data="export_files")],
            [Button.inline("📦 Send as .zip file", data="export_zip")]
        ]
        await event.respond(
            f"🎉 **Login completed for {total_success} account(s)!**\n\n"
            "How would you like to receive your session files?",
            buttons=buttons
        )
        return

    phone = data["numbers"][data["current_index"]]
    clean_phone = phone.replace("+", "").replace(" ", "").strip()
    session_name = f"session_{clean_phone}"

    await event.respond(f"⏳ **[{data['current_index'] + 1}/{len(data['numbers'])}] Sending OTP to:** `{phone}`")

    client = TelegramClient(session_name, API_ID, API_HASH)
    await client.connect()

    try:
        sent_code = await client.send_code_request(phone)
        data.update({
            "client": client,
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash,
            "state": "AWAITING_OTP"
        })
        await event.respond(f"📩 **OTP sent to {phone}!**\nPlease enter the OTP code:")
    except Exception as e:
        await event.respond(f"❌ Error for `{phone}`: `{e}`. Moving to next number...")
        await client.disconnect()
        clean_file(f"{session_name}.session")
        data["current_index"] += 1
        await process_next_number(event, chat_id)

# ----------------- MAIN MESSAGE HANDLER -----------------

@bot.on(events.NewMessage)
async def message_handler(event):
    chat_id = event.chat_id

    if event.text and (event.text.startswith("/start") or event.text.startswith("/redeem") or event.text.startswith("/genkey") or event.text.startswith("/cancel")):
        return

    if not is_user_active(chat_id):
        await event.respond(
            "⚠️ **Access Denied!**\n\n"
            "TO Get Key\n"
            "dm : - @cring7x\n\n"
            "🔑 Activate Key Using: `/redeem YOUR_KEY`"
        )
        return

    text = event.text.strip() if event.text else ""
    kb = ADMIN_KEYBOARD if chat_id == ADMIN_ID else MAIN_KEYBOARD

    # Admin Quick Buttons
    if chat_id == ADMIN_ID:
        if text == "🔑 Gen 1 Day":
            key = generate_key_action(1)
            await event.respond(f"🔑 **1-Day Key Generated!**\n\n🎟️ Key: `{key}`", buttons=kb)
            return
        elif text == "🔑 Gen 7 Days":
            key = generate_key_action(7)
            await event.respond(f"🔑 **7-Days Key Generated!**\n\n🎟️ Key: `{key}`", buttons=kb)
            return
        elif text == "🔑 Gen 30 Days":
            key = generate_key_action(30)
            await event.respond(f"🔑 **30-Days Key Generated!**\n\n🎟️ Key: `{key}`", buttons=kb)
            return

    # Menu Buttons Navigation
    if text == "➕ Create Session":
        user_sessions[chat_id] = {
            "numbers": [],
            "current_index": 0,
            "client": None,
            "phone": None,
            "phone_code_hash": None,
            "generated_files": [],
            "state": "AWAITING_NUMBERS"
        }
        await event.respond("➕ **Create Sessions Mode**\n\nSend your phone numbers (one per line):", buttons=kb)
        return

    elif text == "📩 Read OTP":
        user_sessions[chat_id] = {"state": "AWAITING_OTP_FILE"}
        await event.respond("📩 **Read OTP Mode**\n\nPlease upload your `.session` file or `.zip` file:", buttons=kb)
        return

    elif text == "🔍 Check Session":
        user_sessions[chat_id] = {"state": "AWAITING_CHECK_FILE"}
        await event.respond("🔍 **Check Session Mode**\n\nPlease upload your `.session` file or `.zip` file:", buttons=kb)
        return

    elif text == "🚫 Check Spam":
        user_sessions[chat_id] = {"state": "AWAITING_SPAM_FILE"}
        await event.respond("🚫 **Check Spam Mode**\n\nPlease upload your `.session` file or `.zip` file:", buttons=kb)
        return

    elif text == "✂️ Split Sessions":
        user_sessions[chat_id] = {"state": "AWAITING_SPLIT_FILE", "extracted_sessions": []}
        await event.respond("✂️ **Split Sessions Mode**\n\nPlease upload a `.zip` file containing session files:", buttons=kb)
        return

    elif text == "🧩 Merge Sessions":
        user_sessions[chat_id] = {"state": "AWAITING_MERGE_FILE"}
        await event.respond("🧩 **Merge Sessions Mode**\n\nPlease upload your `.session` files or `.zip` files to merge into ONE single ZIP file:", buttons=kb)
        return

    if chat_id not in user_sessions:
        await event.respond("Please select an option from the menu below:", buttons=kb)
        return

    data = user_sessions[chat_id]
    state = data.get("state")

    # ---------------- HANDLE SPLIT STEP 2 (COUNT INPUT) ----------------
    if state == "AWAITING_SPLIT_COUNT" and text.isdigit():
        split_size = int(text)
        sessions = data.get("extracted_sessions", [])
        
        if split_size <= 0:
            await event.respond("❌ Please enter a number greater than 0.")
            return

        await event.respond(f"✂️ Splitting {len(sessions)} sessions into chunks of {split_size}...")
        
        # Chunking sessions
        chunks = [sessions[i:i + split_size] for i in range(0, len(sessions), split_size)]
        
        for idx, chunk in enumerate(chunks, 1):
            date_str = datetime.now().strftime("%H%M%S")
            part_zip = f"Split_Part_{idx}_({len(chunk)}_Sessions)_{date_str}.zip"
            
            with zipfile.ZipFile(part_zip, 'w') as zipf:
                for sess in chunk:
                    if os.path.exists(sess):
                        zipf.write(sess, arcname=os.path.basename(sess))
            
            await bot.send_file(
                chat_id,
                part_zip,
                caption=f"📦 **Split File {idx}**\n📁 Total Sessions inside: `{len(chunk)}`"
            )
            clean_file(part_zip)

        for sess in sessions:
            clean_file(sess)

        del user_sessions[chat_id]
        await event.respond("✅ **All split files sent successfully!**", buttons=kb)
        return

    # ---------------- FILE UPLOADS HANDLING ----------------
    if event.document and state in ["AWAITING_OTP_FILE", "AWAITING_CHECK_FILE", "AWAITING_SPAM_FILE", "AWAITING_SPLIT_FILE", "AWAITING_MERGE_FILE"]:
        file_path = await event.download_media()
        sessions = extract_session_files(file_path)

        if not sessions:
            await event.respond("❌ No valid `.session` files found in the upload.", buttons=kb)
            clean_file(file_path)
            return

        if state == "AWAITING_SPLIT_FILE":
            data["extracted_sessions"] = sessions
            data["state"] = "AWAITING_SPLIT_COUNT"
            await event.respond(
                f"📥 **Total Sessions Found:** `{len(sessions)}`\n\n"
                f"How many sessions do you want in each file? (e.g., send `20` to get a file of 20, and the remaining in another file):"
            )
            clean_file(file_path)
            return

        elif state == "AWAITING_MERGE_FILE":
            await event.respond(f"🧩 Merging all `{len(sessions)}` sessions into a single ZIP file...")
            total_accounts = len(sessions)
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"Merged_All_{total_accounts}_Sessions_{date_str}.zip"

            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for sess in sessions:
                    if os.path.exists(sess):
                        zipf.write(sess, arcname=os.path.basename(sess))

            await bot.send_file(
                chat_id,
                zip_filename,
                caption=f"🎉 **Merged Single Package Ready!**\n📁 Total Sessions: `{total_accounts}`"
            )

            clean_file(zip_filename)
            for sess in sessions:
                clean_file(sess)

            await event.respond("✅ **Single Merged ZIP sent successfully!**", buttons=kb)

        elif state == "AWAITING_OTP_FILE":
            await event.respond(f"🔎 Reading messages from `{len(sessions)}` session(s)...")
            for sess in sessions:
                sess_name = os.path.splitext(sess)[0]
                temp_client = TelegramClient(sess_name, API_ID, API_HASH)
                try:
                    await temp_client.connect()
                    if await temp_client.is_user_authorized():
                        me = await temp_client.get_me()
                        msgs = await temp_client.get_messages(777000, limit=2)
                        otp_text = "No recent OTP found."
                        if msgs:
                            otp_text = "\n".join([m.message for m in msgs if m.message])

                        await event.respond(
                            f"📱 **Phone:** `+{me.phone}`\n"
                            f"👤 **Name:** {me.first_name}\n"
                            f"📩 **Recent Messages/OTP:**\n`{otp_text}`"
                        )
                    else:
                        await event.respond(f"⚠️ Session expired or invalid for: `{os.path.basename(sess)}`")
                    await temp_client.disconnect()
                except Exception as e:
                    await event.respond(f"❌ Error reading `{os.path.basename(sess)}`: `{e}`")
                finally:
                    clean_file(sess)

        elif state == "AWAITING_CHECK_FILE":
            await event.respond(f"🔍 Checking status for `{len(sessions)}` session(s)...")
            results = []
            for sess in sessions:
                sess_name = os.path.splitext(sess)[0]
                temp_client = TelegramClient(sess_name, API_ID, API_HASH)
                try:
                    await temp_client.connect()
                    if await temp_client.is_user_authorized():
                        me = await temp_client.get_me()
                        results.append(f"✅ `+{me.phone}` -> **GOOD / ACTIVE**")
                    else:
                        results.append(f"❌ `{os.path.basename(sess)}` -> **EXPIRED / INVALID**")
                    await temp_client.disconnect()
                except (UserDeactivatedError, UserDeactivatedBanError):
                    results.append(f"🚫 `{os.path.basename(sess)}` -> **BANNED / FROZEN**")
                except AuthKeyUnregisteredError:
                    results.append(f"❌ `{os.path.basename(sess)}` -> **DEACTIVATED / TERMINATED**")
                except Exception as e:
                    results.append(f"⚠️ `{os.path.basename(sess)}` -> **ERROR: {e}**")
                finally:
                    clean_file(sess)

            report = "\n".join(results)
            await event.respond(f"📊 **Session Status Report:**\n\n{report}", buttons=kb)

        elif state == "AWAITING_SPAM_FILE":
            await event.respond(f"🚫 Checking SpamBot restriction for `{len(sessions)}` session(s)...")
            results = []
            for sess in sessions:
                sess_name = os.path.splitext(sess)[0]
                temp_client = TelegramClient(sess_name, API_ID, API_HASH)
                try:
                    await temp_client.connect()
                    if await temp_client.is_user_authorized():
                        me = await temp_client.get_me()
                        
                        async with temp_client.conversation("@SpamBot", timeout=12) as conv:
                            await conv.send_message("/start")
                            resp = await conv.get_response()
                            resp_text = resp.text if resp else ""
                            
                            is_good = (
                                "Good news" in resp_text or 
                                "free as a bird" in resp_text or 
                                "anti-spam systems" in resp_text
                            )
                            
                            if is_good:
                                results.append(f"🟢 `+{me.phone}` -> **GOOD / CLEAN**")
                            else:
                                results.append(f"🔴 `+{me.phone}` -> **SPAM / RESTRICTED**")
                    else:
                        results.append(f"❌ `{os.path.basename(sess)}` -> **EXPIRED SESSION**")
                    await temp_client.disconnect()
                except Exception as e:
                    results.append(f"⚠️ `{os.path.basename(sess)}` -> **ERROR: {e}**")
                finally:
                    clean_file(sess)

            report = "\n".join(results)
            await event.respond(f"📋 **Spam Status Report:**\n\n{report}", buttons=kb)

        clean_file(file_path)
        del user_sessions[chat_id]
        return

    if state == "AWAITING_NUMBERS":
        raw_text = event.text.strip()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        
        if not lines:
            await event.respond("❌ Invalid input! Please send valid phone numbers.")
            return

        data["numbers"] = lines
        data["current_index"] = 0
        await event.respond(f"📋 Received {len(lines)} number(s). Starting login process...")
        await process_next_number(event, chat_id)

    elif state == "AWAITING_OTP":
        otp = event.text.replace(" ", "").replace("-", "").strip()
        client = data["client"]
        phone = data["phone"]
        code_hash = data["phone_code_hash"]

        try:
            await client.sign_in(phone, code=otp, phone_code_hash=code_hash)
            await client.disconnect()

            clean_phone = phone.replace("+", "").replace(" ", "").strip()
            file_path = f"session_{clean_phone}.session"

            data["generated_files"].append(file_path)

            data["current_index"] += 1
            await process_next_number(event, chat_id)

        except SessionPasswordNeededError:
            data["state"] = "AWAITING_2FA"
            await event.respond("🔐 **2FA Password Required!** Please enter your password:")
        except (PhoneCodeInvalidError, PhoneCodeExpiredError):
            await event.respond("❌ Invalid OTP code. Please enter the correct OTP:")
        except Exception as e:
            await event.respond(f"❌ Login failed: `{e}`")
            await client.disconnect()
            clean_phone = phone.replace("+", "").replace(" ", "").strip()
            clean_file(f"session_{clean_phone}.session")
            data["current_index"] += 1
            await process_next_number(event, chat_id)

    elif state == "AWAITING_2FA":
        password = event.text.strip()
        client = data["client"]
        phone = data["phone"]

        try:
            await client.sign_in(password=password)
            await client.disconnect()

            clean_phone = phone.replace("+", "").replace(" ", "").strip()
            file_path = f"session_{clean_phone}.session"

            data["generated_files"].append(file_path)

            data["current_index"] += 1
            await process_next_number(event, chat_id)

        except PasswordHashInvalidError:
            await event.respond("❌ Incorrect 2FA password. Try again:")
        except Exception as e:
            await event.respond(f"❌ Login error: `{e}`")
            await client.disconnect()
            clean_phone = phone.replace("+", "").replace(" ", "").strip()
            clean_file(f"session_{clean_phone}.session")
            data["current_index"] += 1
            await process_next_number(event, chat_id)

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    chat_id = event.chat_id
    kb = ADMIN_KEYBOARD if chat_id == ADMIN_ID else MAIN_KEYBOARD
    
    if not is_user_active(chat_id):
        await event.answer("⚠️ Subscription expired or invalid!", alert=True)
        return

    if event.data == b"export_files":
        data = user_sessions.get(chat_id, {})
        generated_files = data.get("generated_files", [])
        await event.edit("📁 **Sending session files...**")
        for file_path in generated_files:
            if os.path.exists(file_path):
                await bot.send_file(
                    chat_id,
                    file_path,
                    caption=f"📄 `{os.path.basename(file_path)}`"
                )
                clean_file(file_path)
        
        await event.respond("✅ **All session files delivered successfully!**", buttons=kb)
        if chat_id in user_sessions:
            del user_sessions[chat_id]

    elif event.data == b"export_zip":
        data = user_sessions.get(chat_id, {})
        generated_files = data.get("generated_files", [])
        await event.edit("📦 **Packing session files into ZIP...**")
        total_accounts = len(generated_files)
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        zip_filename = f"Sessions_{total_accounts}_Accounts_{date_str}.zip"

        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for file_path in generated_files:
                if os.path.exists(file_path):
                    zipf.write(file_path, arcname=os.path.basename(file_path))

        await bot.send_file(
            chat_id,
            zip_filename,
            caption=f"🎉 **ZIP Package Ready!**\n📁 Total Accounts: `{total_accounts}`"
        )

        clean_file(zip_filename)
        for file_path in generated_files:
            clean_file(file_path)

        await event.respond("✅ **Process completed successfully!**", buttons=kb)
        if chat_id in user_sessions:
            del user_sessions[chat_id]

print("BotStatus: ONLINE")
bot.run_until_disconnected()