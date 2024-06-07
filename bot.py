# !/usr/bin/env python
# -*- coding: utf-8 -*

import asyncio, html2text, logging, os, re, requests, datetime
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from db import get_session, Summarize
from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy import func

from telegram import constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Configure the logging;
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Configure user-agent for requests;
userAgent = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"

# Configure the html2text;
h2t = html2text.HTML2Text()
h2t.ignore_tables = True
h2t.ignore_images = True
h2t.google_doc = True

# Load the environment variables;
logging.info("Loading the environment variables...")
# Clear all the environment variables;
os.environ.clear()
# Load the environment variables from the .env file;
load_dotenv()
# Create an OpenAI client;
try:
    aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except:
    logging.error("The OPENAI_API_KEY environment variable is not set.")
    exit(1)
try:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
except:
    logging.error("The TELEGRAM_BOT_TOKEN environment variable is not set.")
    exit(1)
try:
    ADMIN_USER_IDS = list(map(int, os.getenv("ADMIN_USER_IDS").split(",")))
except:
    logging.error("The ADMIN_USER_IDS environment variable is not set.")
    exit(1)
try:
    ALLOWED_TELEGRAM_USER_IDS = list(map(int, os.getenv("ALLOWED_TELEGRAM_USER_IDS").split(",")))
except:
    ALLOWED_TELEGRAM_USER_IDS = []
logging.info("Environment variables loaded.")

prompt = """
- You are a seasoned summary expert, capable of condensing and summarizing given articles, papers, or posts, accurately conveying the main idea to make the content easier to understand.

- You place great emphasis on user experience, never adding irrelevant content like "Summary," "The summary is as follows," "Original text," "You can check the original text if interested," or "Original link." Your summaries always convey the core information directly.
- You place great emphasis on user experience, never adding irrelevant content like "Summary," "The summary is as follows," "Original text," "You can check the original text if interested," or "Original link." Your summaries always convey the core information directly.
- You place great emphasis on user experience, never adding irrelevant content like "Summary," "The summary is as follows," "Original text," "You can check the original text if interested," or "Original link." Your summaries always convey the core information directly.
- You always accurately convey the main idea of the original text, succinctly summarizing the core points of the article, and your concise and precise summaries always avoid empty words and clichés.
- You are adept at handling various large, small, and even chaotic text content, always accurately extracting key information and summarizing the core content globally to make it easier to understand.
"""

async def handleStartMessage(update, context):
    userId = update.message.from_user.id
    logging.info(f"User {userId} started the bot.")
    if userId in ADMIN_USER_IDS:
        await update.message.reply_text("Hey boss, I'm ready to serve you :)")
    elif userId in ALLOWED_TELEGRAM_USER_IDS:
        await update.message.reply_text("Hello! I'm Summarize bot, forword the message to me and I will summarize it for you :)")
    else:
        await update.message.reply_text("Sorry, you are not allowed to use this bot, please contact my owner to get the permission.")
    return

async def handleHelpMessage(update, context):
    userId = update.message.from_user.id
    logging.info(f"User {userId} requested help.")
    if userId in ADMIN_USER_IDS or userId in ALLOWED_TELEGRAM_USER_IDS:
        await update.message.reply_text("Hello! I'm Summarize bot, available commands:\n\n/help - Show this help message.\n/purge - Purge the cached content from the database.\n/summarize - Summarize the target message.\n\nOr you can just forward the message to me and I will summarize it for you :)")
    else:
        await update.message.reply_text("Sorry, you are not allowed to use this bot, please contact my owner to get the permission.")
    return

async def handleRequest(update, context):
    userId = update.message.from_user.id
    logging.info(f"User {userId} sent a message.")
    if update.message.chat.type == "private":
        if userId not in ADMIN_USER_IDS and userId not in ALLOWED_TELEGRAM_USER_IDS:
            await update.message.reply_text("Sorry, you are not allowed to use this bot, please contact my owner to get the permission.")
            return

    # Message entities handler;
    entityUrl = ""
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type == "text_link":
                entityUrl = entity.url
                logging.info(f"Entity URL: {entityUrl}")

    if entityUrl:
        url = entityUrl
    else:
        urls = re.findall(r'(https?://[^\s]+)', update.message.text)
        if urls:
            url = urls[0]
        else:
            await update.message.reply_text("I can't handle this.")
            return
        await anySummarize(update, context, url)

# Function to force delete cached content from database;
async def handlePurgeCommand(update, context):
    userId = update.message.from_user.id
    logging.info(f"User {userId} sent a purge command.")
    # Get the target message from reply;
    if not update.message.reply_to_message:
        await update.message.reply_text("Please reply to the message you wanna clear the cache.")
        return
    # Check if the target is already cached;
    # If so, delete the cached content;
    # If not, return;
    session = get_session()
    try:
        urls = re.findall(r'(https?://[^\s]+)', update.message.reply_to_message.text)
        if urls:
            id = urls[0]
            anyLinkItem = session.query(Summarize).filter_by(id=id).first()
            session.delete(anyLinkItem)
            session.commit()
            session.close()
            await update.message.reply_text("Clear the cache successfully.")
        else:
            session.close()
            await update.message.reply_text("Can't find the target content.")
    except:
        session.close()
        await update.message.reply_text("Can't find the target content.")
    return

async def handleSummarizeCommand(update, context):
    # Logging for user private message or group message;
    if update.message.chat.type == "private":
        userId = update.message.from_user.id
        logging.info(f"User {userId} sent a message.")
        if userId not in ADMIN_USER_IDS and userId not in ALLOWED_TELEGRAM_USER_IDS:
            await update.message.reply_text("Sorry, you are not allowed to use this bot, please contact the owner to get the permission.")
            return
    else:
        chatId = update.message.chat.id
        logging.info(f"Group {chatId} sent a command.")
    # Handle the command;
    # Check if any link in the text or entities;
    entityUrl = ""
    if update.message.reply_to_message:
        # This is a reply to another message, extract URL from that message;
        if update.message.reply_to_message.entities:
            for entity in update.message.reply_to_message.entities:
                if entity.type == "text_link":
                    entityUrl = entity.url
                    logging.info(f"Entity URL: {entityUrl}")
        if entityUrl:
            url = entityUrl
        else:
            try:
                urls = re.findall(r'(https?://[^\s]+)', update.message.reply_to_message.text)
                if urls:
                    url = urls[0]
            except:
                await update.message.reply_text("I can't handle this.")
                return
    else:
        if update.message.entities:
            for entity in update.message.entities:
                if entity.type == "text_link":
                    entityUrl = entity.url
                    logging.info(f"Entity URL: {entityUrl}")
        if entityUrl:
            url = entityUrl
        else:
            urls = re.findall(r'(https?://[^\s]+)', update.message.text)
            if urls:
                url = urls[0]
            else:
                await update.message.reply_text("I can't handle this.")
                return
    await anySummarize(update, context, url)

async def anySummarize(update, context, url):
    logging.info("Summarizing the message from any link...")
    replyMessage = await update.message.reply_text("Processing...")
    # Use full url link as id;
    id = url

    # Check if the article is already in the database;
    session = get_session()
    try:
        anyLinkItem = session.query(Summarize).filter_by(id=id).first()
        summary = anyLinkItem.summary
        logging.info("The article is already in the database, sending the summary...")
        await replyMessage.edit_text(summary, parse_mode="Markdown")
        session.close()
        logging.info("The summary has been sent.")
        return
    except:
        pass

    # Fetch the article content;
    title, content = await fetchContent(url, replyMessage, "title")
    content = f"Hi, please summartize the article: {title}\n\n```\n" + content + "\n```"
    await handleOpenAiRequest(update, content, id, replyMessage, title, "anyLink")

async def fetchContent(url, replyMessage, summaryType):
    # Check if the target url is a redirect link;
    response = requests.get(url, headers={"User-Agent": userAgent}, allow_redirects=False)
    logging.info(f"Response status code: {response.status_code}")
    # Extract title if needed;
    title = None
    if summaryType == "title":
        if response.status_code == 200:
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            title = soup.find('title')
            if title:
                title = title.get_text()
                logging.info(f"The title is {title}.")
    # Here we use the location header as the real url, status code include 301, 302, 303, 307, 308;
    if response.status_code in [301, 302, 303, 307, 308]:
        url = response.headers['Location']
        logging.info(f"Redirect location: {url}")
        # If the location is targeted to X (formerly Twitter), then use `fxtwitter.com` instead;
        if "twitter.com" in url:
            url = url.replace("twitter.com", "fxtwitter.com")
            logging.info(f"Target location: {url}")
            response = requests.get(url, allow_redirects=False)
        else:
            response = requests.get(url, headers={"User-Agent": userAgent})
    if response.status_code != 200:
        await replyMessage.edit_text("Seems I got blocked by the site or the site is down, please try again lat")
        return
    # Check if the site is a Mastodon instance;
    # Here we use the `mastodon` keyword in html head `script id="initial-state"` part to identify Mastodon instances;
    try:
        htmlHead = response.text.split("<head>")[1].split("</head>")[0]
        initialState = re.search(r'script id="initial-state"[^<]+', htmlHead)
    except:
        initialState = None
    if initialState and "mastodon" in initialState.group():
        # If the site is a Mastodon instance, then get the content from `meta content` part from html head;
        # And here may have more than one `meta content` part, so we need to get all of them;
        metaContents = re.findall(r'meta content="[^"]+"', htmlHead)
        content = ""
        for metaContent in metaContents:
            content += metaContent.split('="')[1].split('"')[0] + "\n"
        return content
    if "JavaScript is not available." in response.text:
        await replyMessage.edit_text("Sorry, I can't handle this page, because it requires JavaScript to be enabled.")
        return
    content = response.text
    try:
        content = h2t.handle(content)
    except:
        pass
    if len(content) > 10000:
        content = content[:10000]
    return title, content

async def handleOpenAiRequest(update, content, id, replyMessage, title, summaryType):
    logging.info(f"Getting summary for user with ID: {update.message.from_user.id}")
    messages=[
        {
            "role": "system",
            "content": prompt
        },
        {
            "role": "user",
            "content": content
        }
    ]
    response = await connectOpenAi(messages)
    await processSummary(update, response, id, replyMessage, title, summaryType)

async def connectOpenAi(messages):
    for attempt in range(2):
        try:
            response = await aclient.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=messages,
                stream=True
            )
            return response
        except:
            logging.error(f"OpenAI request failed, retrying...")
            await asyncio.sleep(2**attempt)
    logging.error("Failed after 2 retries.")
    return "API error!"

async def processSummary(update, response, id, replyMessage, title, summaryType):
    # If the response is error message;
    if response == "API error!":
        logging.error("Failed to connect to the OpenAI API.")
        await replyMessage.edit_text("Something wrong with the OpenAI API, please try again later.")
        return

    logging.info(f"Processing OpenAI response for user with ID: {update.message.from_user.id}")
    await update.message.reply_chat_action(constants.ChatAction.TYPING)

    messagesList = []
    tempString = ""

    # Process the response;
    async for chunk in response:
        if chunk.choices[0].delta.content:
            tempString += chunk.choices[0].delta.content
            if len(tempString) >= 50:  # Edit the message every 50 characters;
                # Remove `\n` from tempString;
                tempString = tempString.replace("\n", "")
                messagesList.append(tempString)
                try:
                    await replyMessage.edit_text("".join(messagesList), parse_mode="Markdown")
                except:
                    pass
                tempString = ""  # Reset the temporary string;

    # Handle remaining text;
    if tempString:
        messagesList.append(tempString)
        try:
            await replyMessage.edit_text("".join(messagesList), parse_mode="Markdown")
        except:
            pass

    # Save the summary to the database;
    session = get_session()
    result = Summarize(id=id, summary="".join(messagesList), title=title, type=summaryType)
    session.add(result)
    session.commit()
    session.close()

if __name__ == '__main__':
    bot = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", handleStartMessage))
    bot.add_handler(CommandHandler("summarize", handleSummarizeCommand))
    bot.add_handler(CommandHandler("help", handleHelpMessage))
    bot.add_handler(CommandHandler("purge", handlePurgeCommand))
    bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handleRequest))
    bot.run_polling()
