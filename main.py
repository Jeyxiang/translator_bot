from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, Update,
                      InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (Application, MessageHandler, CommandHandler, filters, ConversationHandler,
                          CallbackQueryHandler, ContextTypes)

import sqlite3

## Where token id is stored
from credentials import TOKEN, DB
from constants import LANGUAGE_TO_CODE
from deep_translator import GoogleTranslator

# init default global variable
SRC, TARGET = 'english', 'chinese'

# Define states
SRC_TYPE, TARGET_TYPE = range(2)

def init_db(user_id):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS userinfo (
            id INTEGER PRIMARY KEY,
            src TEXT NOT NULL,
            tgt TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

    update_configurations(user_id, 'english', 'chinese')
    
    return True


def update_configurations(user_id, source, target):
    # reopen connection
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    if len(cur.execute(f'''SELECT id FROM userinfo WHERE id = {user_id}''').fetchall()) > 0:
        # update user config
        cur.execute(f'''UPDATE userinfo SET src = "{source}", tgt = "{target}" WHERE id = {user_id}''')
    else:
        # insert values if user_id not found
        cur.execute(f'''INSERT INTO userinfo (id, src, tgt) VALUES ({user_id},"{source}","{target}")''')
    conn.commit()
    conn.close()
    return True

def get_configurations(user_id):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(f'''SELECT src, tgt FROM userinfo WHERE id = {user_id}''')
    row = cur.fetchone()
    conn.close()
    if row:
        src, tgt = row
        return (src, tgt)
    else:
        return ('auto','english')


def default_keyboard() -> ReplyKeyboardMarkup:
    # Define custom keyboard buttons
    keyboard = [
        ['/help', '/summary', '/configure'],  # First row of buttons
    ]
    # Create a ReplyKeyboardMarkup object
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    return reply_markup


# COMMANDS
async def source_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the source language."""
    query = update.callback_query
    await query.answer()
    context.user_data['SRC'] = query.data

    # logger.info('Car type of %s: %s', user.first_name, update.message.text)
    await query.edit_message_text(
        f'You selected <b>{query.data}</b> as source.\n'
        f'What language do you want to translate to?',
        parse_mode='HTML'
    )
    # Define inline buttons for languages
    keyboard = [[InlineKeyboardButton(key, callback_data=key)] for key in LANGUAGE_TO_CODE.keys()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text('<b>Please choose:</b>', parse_mode='HTML', reply_markup=reply_markup)

    return TARGET_TYPE

async def target_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the target language"""
    query = update.callback_query
    await query.answer()
    src_language = context.user_data.get('SRC')
    target_language = query.data
    if src_language == 'auto':
        src_language = 'english'
    await query.edit_message_text(
        text=f'You selected <b>{query.data}</b> as your target language.',
        parse_mode='HTML'
    )

    ## UPDATE DB
    user_id = update.effective_user.id
    update_configurations(user_id, src_language, target_language)

    message = f'To view your current configurations, use /summary\n To edit your configurations, use /configure'
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML', reply_markup=default_keyboard())
    return ConversationHandler.END


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Summarizes the user's selections and ends the conversation"""
    user_id = update.effective_user.id
    src, target = get_configurations(user_id)
    # Construct the summary text
    summary_text = (f"Here's your current settings:\n"
                    f"<b>Source language:</b> {src}\n"
                    f"<b>Target language:</b> {target}\n"
                    f"<b>Happy Translating!</b>")
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text=summary_text, parse_mode='HTML', reply_markup=default_keyboard())


async def configure_command(update: Update, context: ContextTypes.DEFAULT_TYPE):   
    """Starts the conversation and asks the user about their preferred car type."""
    await update.message.reply_text(
        'Let\'s get some details about your language preference.\n'
        'What language are you translating?\n'
        'To exit, click /cancel',
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove(),
    )
    reply_keyboard = [[InlineKeyboardButton(key, callback_data=key)] for key in LANGUAGE_TO_CODE.keys()]
    reply_markup = InlineKeyboardMarkup(reply_keyboard)
    await update.message.reply_text('<b>Please choose:</b>', parse_mode='HTML', reply_markup=reply_markup)

    return SRC_TYPE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text('Cancelling...', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END 
    

async def start_command(update, context):
    # insert user id into DB 
    user_id = update.effective_user.id
    init_db(user_id)

    await update.message.reply_text(
        f'<b>Welcome to Translation Bot!</b>',
        parse_mode='HTML',
        reply_markup = default_keyboard()
    )
async def help_command(update, context):
    await update.message.reply_text(
        f'To view your current configurations, use /summary \n'
        f'To edit your configurations, use /configure \n'
        'For better results, it is advisable to select the source language of choice\n'
        f'To start translating, just type in any keyword!',
        parse_mode='HTML',
        reply_markup = default_keyboard()
    )


async def translate_command(update, context):
    text_to_translate = update.message.text
    user_id = update.effective_user.id
    print(f"User ID: {user_id} is translating")

    src, target = get_configurations(user_id)
    text_message = GoogleTranslator(source=LANGUAGE_TO_CODE[src], target=LANGUAGE_TO_CODE[target]).translate(text_to_translate)
    await update.message.reply_text(
        text_message,
        parse_mode='HTML',
        reply_markup = default_keyboard()
    )

async def default_reply(update, context):
    await update.message.reply_text('Sorry I can only process text messages for now!')

async def error(update: Update, context):
    print(f'Update {update} caused error {context.error}')


def main() -> None:
    """Run the bot."""
    token = TOKEN
    application = Application.builder().token(token).concurrent_updates(True).read_timeout(30).write_timeout(30).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('configure', configure_command)],
        states={
            SRC_TYPE: [CallbackQueryHandler(source_type)],
            TARGET_TYPE: [CallbackQueryHandler(target_type)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)

    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('summary', summary_command))

    # Translation
    application.add_handler(MessageHandler(filters.TEXT, translate_command))
    application.add_handler(MessageHandler(filters.PHOTO, default_reply))

    application.add_error_handler(error)

    print("Telegram Bot started!", flush=True)
    application.run_polling()


if __name__ == '__main__':
    main()

