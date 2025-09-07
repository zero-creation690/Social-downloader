import os
import yt_dlp
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Your bot token
TOKEN = '8285386422:AAFDppdScIBbgGMsopzKx7H1zut1JnnuP50'

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Dictionary to keep track of user-selected URLs
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    user_first_name = update.effective_user.first_name
    greeting = (
        f"👋 Hello there, {user_first_name}! 🎉\n\n"
        "I'm a bot that can download videos and audio for you. 📲\n\n"
        "Just send me a link from YouTube, Instagram, TikTok, Facebook, or Pinterest, and I'll do the rest! ✨"
    )
    await update.message.reply_text(greeting)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command."""
    help_text = (
        "🤖 **How to use me:**\n\n"
        "1. Send me a valid link from YouTube, Instagram, TikTok, Facebook, or Pinterest.\n"
        "2. I'll check the available video and audio formats.\n"
        "3. You'll see buttons to choose the resolution or to download as an MP3 file.\n"
        "4. Click your desired option, and I'll send you the file!\n\n"
        "Happy downloading! 🚀"
    )
    await update.message.reply_text(help_text)

def get_available_formats(url: str):
    """Extracts available formats from a given URL."""
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'noplaylist': True,
        'quiet': True,
    }
    formats = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Use a set to avoid duplicate resolutions
            processed_resolutions = set()

            for f in info['formats']:
                # Filter for video formats with both video and audio streams
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    resolution = f.get('resolution', 'Unknown')
                    # If resolution is 'Unknown', try to construct it from width/height
                    if resolution == 'Unknown' and f.get('width') and f.get('height'):
                        resolution = f"{f['width']}x{f['height']}"

                    if resolution not in processed_resolutions:
                        formats.append({
                            'format_id': f['format_id'],
                            'resolution': resolution
                        })
                        processed_resolutions.add(resolution)
            
            # Sort formats by resolution
            formats.sort(key=lambda x: int(x['resolution'].split('x')[0]) if 'x' in x['resolution'] else 0, reverse=True)

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"DownloadError extracting info for {url}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error extracting info for {url}: {e}")
        return []

    return formats

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles a message containing a URL."""
    url = update.message.text
    if any(platform in url for platform in ["youtube.com", "instagram.com", "tiktok.com", "facebook.com", "pinterest.com"]):
        await update.message.reply_text("🔎 Analyzing link... This might take a moment. ⏳")
        formats = get_available_formats(url)
        user_data[update.effective_user.id] = url

        if formats:
            buttons = [
                [InlineKeyboardButton(f"🎬 {f['resolution']}", callback_data=f"{f['format_id']}")]
                for f in formats
            ]
            buttons.append([InlineKeyboardButton("🎧 Download as MP3", callback_data="mp3")])
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text("✅ Link analyzed! Select your preferred format: 👇", reply_markup=reply_markup)
        else:
            await update.message.reply_text("⚠️ Oh no! No video formats were found for this link. It might be a private video or an unsupported type. Try another link! 💔")
    else:
        await update.message.reply_text("🚫 Please send a valid link from YouTube, Instagram, TikTok, Facebook, or Pinterest. I can't process that. 😔")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the video download request from a callback query."""
    query = update.callback_query
    await query.answer()

    format_id = query.data
    user_id = query.from_user.id
    url = user_data.get(user_id)

    if not url:
        await query.edit_message_text("❌ Error: I've lost the link! Please try sending it again. 🔄")
        return

    if format_id == 'mp3':
        await download_mp3(update, context)
        return

    message = await query.edit_message_text("⏳ Downloading the video... Please wait a moment! 🙏")

    try:
        ydl_opts = {
            'format': format_id,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
        }
        
        # Ensure the 'downloads' directory exists
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        await message.edit_text("📤 Uploading your video... Almost there! 🚀")
        with open(file_path, 'rb') as file:
            await query.message.reply_video(file, caption=info.get('title', 'Video'))

        await message.delete() # Remove the "Uploading..." message
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        await message.edit_text("❌ An error occurred while downloading or uploading. Please try again. 😥")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        del user_data[user_id]


async def download_mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the MP3 download request from a callback query."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    url = user_data.get(user_id)

    if not url:
        await query.edit_message_text("❌ Error: I've lost the link! Please try sending it again. 🔄")
        return

    message = await query.edit_message_text("🎶 Converting to MP3... Please be patient!  Converting can take some time. ⌛")

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
        }
        
        # Ensure the 'downloads' directory exists
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        await message.edit_text("📤 Uploading your MP3 file... Woo-hoo! 🎉")
        with open(file_path, 'rb') as file:
            await query.message.reply_audio(file, title=info.get('title', 'Audio'))

        await message.delete() # Remove the "Uploading..." message
    except Exception as e:
        logger.error(f"Error downloading MP3: {e}")
        await message.edit_message_text("❌ An error occurred while converting or uploading the MP3. 😔")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        del user_data[user_id]

# The main function for local testing is removed for Vercel deployment,
# but the handlers are still defined here for the webhook script.
# You'll run the webhook handler instead of `main()`.

def setup_bot_handlers(app: Application):
    """Sets up all bot handlers for the application."""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(download_video))
