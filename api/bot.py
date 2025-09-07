import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from http.server import BaseHTTPRequestHandler
import json
import asyncio

# Your bot token. It's best to use environment variables for this.
# For simplicity, I've hardcoded it as you requested, but for a real-world app,
# you should set it in Vercel's environment variables.
TOKEN = '-8285386422:AAFDppdScIBbgGMsopzKx7H1zut1JnnuP50'

# A dictionary to keep track of user-selected URLs and formats
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    greeting = f"👋 Hello, {user_first_name}! 🎉\n\nSend me a link from YouTube, Instagram, TikTok, Facebook, or Pinterest, and I'll download it for you. 📲"
    await update.message.reply_text(greeting)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 **How to use this bot:**\n"
        "1. Send me a link from supported platforms (YouTube, Instagram, TikTok, Facebook, Pinterest).\n"
        "2. I'll analyze the link and present you with download options.\n"
        "3. Choose your preferred video resolution or select the MP3 option.\n"
        "4. I will download and send you the file. Enjoy! ✨"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

def get_available_formats(url: str):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
    }
    formats = []
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                # Handle playlists or channels (though we're set to ignore them, good to be safe)
                info = info['entries'][0]
            
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('resolution') and f.get('resolution') != 'Unknown':
                    formats.append({
                        'format_id': f['format_id'],
                        'resolution': f.get('resolution', 'Unknown')
                    })
            # Remove duplicates based on resolution
            seen = set()
            unique_formats = []
            for f in formats:
                if f['resolution'] not in seen:
                    unique_formats.append(f)
                    seen.add(f['resolution'])
            return unique_formats
            
    except Exception as e:
        print(f"Error getting formats: {e}")
        return []

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    supported_platforms = ["youtube.com", "instagram.com", "tiktok.com", "facebook.com", "pinterest.com"]
    if any(platform in url for platform in supported_platforms):
        await update.message.reply_text("🔍 **Analyzing your link...**", parse_mode='Markdown')
        formats = get_available_formats(url)
        user_data[update.effective_user.id] = url

        if formats:
            buttons = [
                [InlineKeyboardButton(f"🎬 {f['resolution']}", callback_data=f"{f['format_id']}")]
                for f in formats
            ]
            buttons.append([InlineKeyboardButton("🎧 Download as MP3", callback_data="mp3")])
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text("✅ **Success!** Select a resolution or download as MP3:", reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ No video formats available for this link. It might be a private video or an unsupported format.")
    else:
        await update.message.reply_text("🚫 Please send a valid link from YouTube, Instagram, TikTok, Facebook, or Pinterest.")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    format_id = query.data
    user_id = query.from_user.id
    url = user_data.get(user_id)

    if not url:
        await query.edit_message_text("❌ Error: Link not found. Please try sending it again.")
        return

    try:
        await query.edit_message_text("⏳ **Downloading...** This may take a moment! 🚀", parse_mode='Markdown')
        
        # Download video with selected format
        ydl_opts = {
            'format': format_id,
            'outtmpl': f'/tmp/%(title)s.%(ext)s',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        await query.edit_message_text("📤 **Uploading your video...** Hang tight! 🚀", parse_mode='Markdown')
        with open(file_path, 'rb') as file:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=file,
                caption="Here's your video! ✨"
            )
        
        os.remove(file_path)
        del user_data[user_id]
        
    except Exception as e:
        print(f"Error downloading video: {e}")
        await query.edit_message_text("❌ Oh no! An error occurred while downloading or uploading the video. Please try another link or contact support. 😢")
        if user_id in user_data:
            del user_data[user_id]


async def download_mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    url = user_data.get(user_id)

    if not url:
        await query.edit_message_text("❌ Error: Link not found. Please try sending it again.")
        return

    try:
        await query.edit_message_text("⏳ **Converting to MP3...** This may take a moment! 🎶", parse_mode='Markdown')
        
        # Download audio and convert to MP3
        ydl_opts = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': f'/tmp/%(title)s.%(ext)s',
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        # Correct the file path to have a .mp3 extension
        base, _ = os.path.splitext(file_path)
        mp3_path = base + ".mp3"

        await query.edit_message_text("📤 **Uploading your MP3 file...** 🎧", parse_mode='Markdown')
        with open(mp3_path, 'rb') as file:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=file,
                caption="Here's your audio! ✨"
            )
        
        os.remove(mp3_path)
        del user_data[user_id]

    except Exception as e:
        print(f"Error downloading MP3: {e}")
        await query.edit_message_text("❌ Oh no! An error occurred while downloading or uploading the MP3. Please try another link. 😢")
        if user_id in user_data:
            del user_data[user_id]

# Main function to handle the webhook
async def main(request):
    try:
        data = await request.json()
        update = Update.de_json(data, Bot(TOKEN))

        application = Application.builder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(download_video, pattern=r'^\d+$'))
        application.add_handler(CallbackQueryHandler(download_mp3, pattern=r'^mp3$'))

        await application.process_update(update)

        return {"statusCode": 200, "body": "OK"}
    except Exception as e:
        print(f"Error processing update: {e}")
        return {"statusCode": 500, "body": "Internal Server Error"}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        asyncio.run(main(json.loads(post_data)))
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

if __name__ == '__main__':
    from http.server import HTTPServer
    server = HTTPServer(('localhost', 8080), handler)
    print("Starting server...")
    server.serve_forever()
