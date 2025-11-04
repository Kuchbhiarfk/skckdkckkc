import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
import json
import base64
from uuid import uuid4
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from datetime import datetime, timezone
from collections import defaultdict
from urllib.parse import quote

# ==== Config (Use Environment Vars) ====
API_HASH="2daa157943cb2d76d149c4de0b036a99"
API_ID=23713783
BOT_TOKEN = "7619023501:AAGBgYZs84QQKSlo0DFl_LULPe--_LHQ2UQ"
CHANNEL_ID = -1003132883596       # <-- Sirf Channel ID daal (koi link nahi)
BOT_USERNAME = "Schedulesfbot"
DECRYPT_URL_BASE = "https://dekhosekdop.onrender.com/op?data="

# Encryption Config
ENCRYPTION_KEY = bytes.fromhex('0123456789abcdef0123456789abcdef')
IV = b'abcdef9876543210'

# ==== Bot Client (Global) ====
bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# States (Global)
user_states = {}
user_temp_data = {}

# ==== Encrypt ====
def encrypt_json_item(data: dict) -> str:
    json_str = json.dumps(data)
    cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, IV)
    padded_data = pad(json_str.encode('utf-8'), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    iv_base64 = base64.b64encode(IV).decode('utf-8')
    encrypted_base64 = base64.b64encode(encrypted_data).decode('utf-8')
    return f"{iv_base64}:{encrypted_base64}"

# ==== Decrypt ====
def decrypt_json_item(encrypted_str: str) -> dict:
    if ':' not in encrypted_str:
        raise ValueError("Invalid format")
    iv_base64, encrypted_base64 = encrypted_str.split(':', 1)
    iv = base64.b64decode(iv_base64)
    encrypted_data = base64.b64decode(encrypted_base64)
    cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
    padded_data = cipher.decrypt(encrypted_data)
    json_str = unpad(padded_data, AES.block_size).decode('utf-8')
    return json.loads(json_str)

# ==== Download & Decrypt ====
async def download_and_decrypt_json(client: Client, msg) -> tuple[str, str]:
    if not msg.document or not msg.document.file_name.endswith('.json'):
        raise ValueError("Not a JSON file")
    path = await client.download_media(msg)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            encrypted_data = json.load(f)
        decrypted_items = []
        if isinstance(encrypted_data, list):
            for item in encrypted_data:
                if 'encrypted_data' in item:
                    enc_str = item['encrypted_data']
                    if enc_str.startswith(DECRYPT_URL_BASE):
                        enc_str = enc_str[len(DECRYPT_URL_BASE):]
                    decrypted_item = decrypt_json_item(enc_str)
                    decrypted_items.append(decrypted_item)
                else:
                    decrypted_items.append(item)
        else:
            decrypted_items.append(encrypted_data)
        decrypted_json = json.dumps(decrypted_items)
        filename = msg.document.file_name
        return decrypted_json, filename
    finally:
        os.remove(path)

# ==== Generate HTML from JSON ====
async def generate_html_from_json(client: Client, original_msg, batch_title: str, batch_thumbnail: str):
    path = await client.download_media(original_msg)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        json_data_str = json.dumps(json_data).replace("False", "false")
        json_data = json.loads(json_data_str)
        batch_name = batch_title
        classes = []
        for item in json_data:
            encrypted_item = encrypt_json_item(item)
            url_wrapped = f"{DECRYPT_URL_BASE}{quote(encrypted_item)}"
            live_at_time = item['live_at_time']
            if live_at_time.endswith('Z'):
                dt = datetime.fromisoformat(live_at_time[:-1] + '+00:00')
            else:
                dt = datetime.fromisoformat(live_at_time)
            date_str = dt.strftime('%Y-%m-%d')
            month_str = dt.strftime('%Y-%m')
            link = url_wrapped
            classes.append({
                'class_name': item['class_name'],
                'teacher_name': item['teacher_name'],
                'date_str': date_str,
                'month_str': month_str,
                'thumbnail': item['thumbnail'],
                'link': link
            })
        day_groups = defaultdict(list)
        teacher_groups = defaultdict(list)
        month_groups = defaultdict(list)
        for c in classes:
            day_groups[c['date_str']].append(c)
            teacher_groups[c['teacher_name']].append(c)
            month_groups[c['month_str']].append(c)
        sorted_days = sorted(day_groups.keys(), reverse=True)
        sorted_teachers = sorted(teacher_groups.keys())
        sorted_months = sorted(month_groups.keys(), reverse=True)
        def generate_chips(lectures):
            chips = ''
            for lec in lectures:
                target = ' target="_blank"' if lec['link'] != '#' else ''
                chips += f'''
                    <a href="{lec["link"]}"{target} class="chip" title="{lec["class_name"]}">
                      <div class="chip-left">
                        <img src="{lec["thumbnail"]}?q=100&w=48&h=48&fit=crop" alt="{lec["teacher_name"]}" class="icon" loading="lazy">
                        <span class="label">{lec["class_name"]}</span>
                      </div>
                      <div class="meta-container">
                        <span class="meta">Teacher: {lec["teacher_name"]}</span>
                        <span class="meta">Date: {lec["date_str"]}</span>
                      </div>
                    </a>
                '''
            return chips
        def generate_section(section_id, title_id, title, content_id, chips, hidden_class=''):
            return f'''
                <section class="section-card{hidden_class}" id="{section_id}" aria-labelledby="{title_id}">
                  <div class="section-head">
                    <h2 class="section-title" id="{title_id}">{title}</h2>
                    <button class="collapse-btn" data-collapse="{section_id}">
                      <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                      <span>Collapse</span>
                    </button>
                  </div>
                  <div class="chip-grid" id="{content_id}">
                    {chips}
                  </div>
                </section>
            '''
        day_sections = ''
        for i, date in enumerate(sorted_days):
            section_id = f"day-wise-{date.replace('-', '')}"
            title_id = f"day-wise-title-{date.replace('-', '')}"
            content_id = f"{section_id}-content"
            chips = generate_chips(day_groups[date])
            day_sections += generate_section(section_id, title_id, date, content_id, chips)
        teacher_sections = ''
        for i, teacher in enumerate(sorted_teachers):
            section_id = f"teacher-wise-{teacher.replace(' ', '_')}"
            title_id = f"teacher-wise-title-{teacher.replace(' ', '_')}"
            content_id = f"{section_id}-content"
            chips = generate_chips(teacher_groups[teacher])
            hidden = ' hidden' if i > 0 else ''
            teacher_sections += generate_section(section_id, title_id, teacher, content_id, chips, hidden)
        month_sections = ''
        for i, month in enumerate(sorted_months):
            section_id = f"month-wise-{month}"
            title_id = f"month-wise-title-{month}"
            content_id = f"{section_id}-content"
            chips = generate_chips(month_groups[month])
            hidden = ' hidden'
            month_sections += generate_section(section_id, title_id, month, content_id, chips, hidden)
        notice_html = f'''
                <!-- Intro notice -->
                <section class="notice" aria-label="Welcome">
                  <div class="title">
                    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" fill="none">
                      <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"></circle>
                      <path d="M12 7v6" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path>
                      <circle cx="12" cy="16.5" r="1" fill="currentColor"></circle>
                    </svg>
                    <span>Welcome to the {batch_title} catalog</span>
                  </div>
                  <div class="image-container">
                    <img src="{batch_thumbnail}" alt="Batch Illustration">
                    <div class="image-caption">{batch_title}</div>
                  </div>
                  <p>Browse lectures by day, teacher, or month using the tabs above.</p>
                </section>
        '''
        full_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{batch_title} — UI clone</title>
  <meta name="description" content="An advanced UI clone of a {batch_title.lower()} catalog with glassmorphism and light/dark mode.">
  <style>
    /* Paste your full CSS here */
  </style>
</head>
<body>
  <header class="site-header">
    <div class="header-inner">
      <div class="brand">
        <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" fill="none">
          <rect x="3" y="3" width="18" height="18" rx="4" stroke="currentColor" stroke-width="2" opacity=".9"></rect>
          <circle cx="12" cy="12" r="3.2" fill="currentColor"></circle>
        </svg>
        <span>{batch_title}</span>
      </div>
      <div class="controls">
        <button class="theme-toggle" aria-label="Toggle theme">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
          </svg>
        </button>
      </div>
    </div>
  </header>

  <div class="tab-bar">
    <div class="tabs" id="tabs">
      <button class="tab" data-target="day-wise" aria-current="true">Day Wise</button>
      <button class="tab" data-target="teacher-wise">Teacher Wise</button>
      <button class="tab" data-target="month-wise">Month Wise</button>
    </div>
  </div>

  <main id="main">
    <div class="wrap">
{notice_html}
{day_sections}
{teacher_sections}
{month_sections}
      <footer>
        UI built as an advanced glassmorphic demo with light/dark mode for educational purposes.
      </footer>
    </div>
  </main>

  <script>
    /* Paste your full JS here */
  </script>
</body>
</html>'''
        return full_html
    finally:
        try:
            os.remove(path)
        except Exception as e:
            print(f"Failed to delete temporary file {path}: {e}")

# ==== Upload HTML Function ====
async def upload_html(client: Client, html_content: str, batch_title: str, chat_id: int) -> 'Message':
    temp_filename = f"{batch_title.replace(' ', '_').lower()}_{uuid4().hex}.html"
    with open(temp_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    sent_msg = await client.send_document(
        chat_id=chat_id,
        document=temp_filename,
        caption=f"Generated HTML Catalog: {batch_title}.html\nOpen in browser to view the interactive catalog! 😁"
    )
    
    try:
        os.remove(temp_filename)
    except Exception as e:
        print(f"Failed to delete temporary file {temp_filename}: {e}")
    
    return sent_msg

# ==== Download & Encrypt (Keep for other features) ====
async def download_and_encrypt_json(client: Client, msg, user_first_name: str, user_id: str, made_at: str) -> tuple[str, str]:
    if not msg.document or not msg.document.file_name.endswith('.json'):
        raise ValueError("Message does not contain a .json file")
    path = await client.download_media(msg)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        encrypted_items = []
        if isinstance(json_data, list):
            for item in json_data:
                item['user_first_name'] = user_first_name
                item['user_id'] = user_id
                item['made_at'] = made_at
                encrypted_item = encrypt_json_item(item)
                encrypted_items.append({"encrypted_data": encrypted_item})
        else:
            json_data['user_first_name'] = user_first_name
            json_data['user_id'] = user_id
            json_data['made_at'] = made_at
            encrypted_item = encrypt_json_item(json_data)
            encrypted_items.append({"encrypted_data": encrypted_item})
        encrypted_json = json.dumps(encrypted_items)
        filename = msg.document.file_name
        return encrypted_json, filename
    finally:
        try:
            os.remove(path)
        except Exception as e:
            print(f"Failed to delete temporary file {path}: {e}")

# ==== Upload Encrypted JSON ====
async def upload_encrypted_json(client: Client, encrypted_json: str, filename: str, chat_id: int) -> 'Message':
    temp_filename = f"encrypted_{uuid4().hex}.json"
    with open(temp_filename, 'w', encoding='utf-8') as f:
        f.write(encrypted_json)
    
    sent_msg = await client.send_document(
        chat_id=chat_id,
        document=temp_filename,
        caption=f"Encrypted JSON: {filename}"
    )
    
    try:
        os.remove(temp_filename)
    except Exception as e:
        print(f"Failed to delete temporary file {temp_filename}: {e}")
    
    return sent_msg

# ==== Force Sub Functions ====
async def get_permanent_link():
    global PERMANENT_INVITE_LINK
    if PERMANENT_INVITE_LINK:
        print("🔗 Using cached permanent link")
        return PERMANENT_INVITE_LINK
    
    try:
        print(f"🔗 Generating permanent invite for main channel {CHANNEL_ID}...")
        link = await bot.export_chat_invite_link(CHANNEL_ID)
        PERMANENT_INVITE_LINK = link
        print(f"✅ Permanent Link: {link}")
        return link
    except Exception as e:
        print(f"❌ Invite Error: {e}")
        return "https://t.me/yourchannel"

async def is_member(user_id):
    try:
        print(f"🔍 Force sub check: User {user_id} in {CHANNEL_ID}...")
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        status = member.status
        print(f"✅ Force sub status: {status}")
        return status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        print(f"❌ Force sub error: {e}")
        return False

async def is_bot_admin_in_channel(target_channel_id):
    try:
        print(f"🔍 Bot admin check in target {target_channel_id}...")
        bot_member = await bot.get_chat_member(target_channel_id, "me")
        status = bot_member.status
        print(f"✅ Bot admin status: {status}")
        return status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        print(f"❌ Bot admin error: {e}")
        return False

# ==== Handlers ====
@bot.on_message(filters.command("genlink"))
async def genlink_start(client, message):
    user_id = message.from_user.id
    user_states[user_id] = {'step': 'waiting_channel'}
    await message.reply_text("Send **channel ID** (e.g., -1001234567890):")

@bot.on_message(filters.command("dec"))
async def dec_start(client, message):
    user_id = message.from_user.id
    user_states[user_id] = {'step': 'waiting_dec_json'}
    await message.reply_text("Send your **encrypted JSON file** (.json):")

@bot.on_message(filters.text)
async def handle_text_step(client, message):
    user_id = message.from_user.id
    if user_id not in user_states:
        return

    state = user_states[user_id]
    text = message.text.strip()

    if state['step'] == 'waiting_channel':
        try:
            channel_id = int(text)
            if channel_id > 0:
                raise ValueError("Negative only!")
            state['channel_id'] = channel_id
            state['step'] = 'waiting_msg'
            await message.reply_text(f"Channel: {channel_id}\nSend **msg ID** (e.g., 123):")
        except ValueError:
            await message.reply_text("Invalid channel ID! Negative integer.")

    elif state['step'] == 'waiting_msg':
        try:
            msg_id = int(text)
            if msg_id <= 0:
                raise ValueError("Positive only!")
            param = f"OP_{state['channel_id']}_{msg_id}"
            url = f"https://t.me/{BOT_USERNAME}?start={param}"
            del user_states[user_id]
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🧪 Test Link", url=url)]])
            await message.reply_text(f"✅ Link: `{url}`", reply_markup=keyboard, parse_mode="Markdown")
        except ValueError:
            await message.reply_text("Invalid msg ID! Positive integer.")

    elif state['step'] == 'waiting_batch_title':
        state['batch_title'] = text
        state['step'] = 'waiting_batch_thumbnail'
        await message.reply_text(f"Batch title set: {text}\nNow enter **batch thumbnail URL**:")
        print(f"Batch title: {text}")

    elif state['step'] == 'waiting_batch_thumbnail':
        state['batch_thumbnail'] = text
        original_msg = user_temp_data[user_id]['original_msg']
        full_html = await generate_html_from_json(bot, original_msg, state['batch_title'], state['batch_thumbnail'])
        sent_msg = await upload_html(bot, full_html, state['batch_title'], user_id)
        await message.reply_text(f"✅ HTML Catalog generated! ID: {sent_msg.id}")
        del user_states[user_id]
        del user_temp_data[user_id]
        print(f"Batch thumbnail: {text}")

@bot.on_message(filters.document)
async def handle_decrypt_step(client, message):
    user_id = message.from_user.id
    if user_id not in user_states or user_states[user_id].get('step') != 'waiting_dec_json':
        return
    try:
        decrypted_json, orig_filename = await download_and_decrypt_json(bot, message)
        sent_msg = await upload_decrypted_json(bot, decrypted_json, orig_filename, user_id)
        await message.reply_text(f"✅ Decrypted JSON uploaded! ID: {sent_msg.id}")
        del user_states[user_id]
    except Exception as e:
        await message.reply_text(f"❌ Decrypt failed: {str(e)}")

# ==== Upload Decrypted JSON ====
async def upload_decrypted_json(client: Client, decrypted_json: str, filename: str, chat_id: int) -> 'Message':
    temp_filename = f"decrypted_{uuid4().hex}.json"
    with open(temp_filename, 'w', encoding='utf-8') as f:
        f.write(decrypted_json)
    sent_msg = await client.send_document(
        chat_id=chat_id,
        document=temp_filename,
        caption=f"Decrypted JSON: {filename}"
    )
    os.remove(temp_filename)
    return sent_msg

# ==== Run Bot (Fixed — Global bot) ====
async def run_bot():
    global bot
    await bot.start()
    print("🚀 Bot is running...")
    await bot.idle()

if __name__ == '__main__':
    asyncio.run(run_bot())
