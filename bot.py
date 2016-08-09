#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import telegram
import sys
from pyslack import SlackClient
import json
import argparse
import time
import os
import traceback
import certifi
import urllib3
import itertools
from datetime import datetime
from pony.orm import db_session, select
from db import botDB, Chat


LAST_UPDATE_ID = None
BOT_DESCRIPTION = "Telegram bot for English courses"
#MESSAGE_START = 'Добро пожаловать! Я бот Proof Space. Пожалуйста, введите "I am ...", где "..." -- выданное Вам кодовое слово, чтобы я понял, из какой Вы группы.'
#MESSAGE_STOP = "Я умолкаю в этом чате! Наберите /start, чтобы вновь подписаться на рассылку анонсов."
SCHEDULE_CMD = u'Расписание'
CARD_CMD = u'Оплата'
STUFF_CMD = u'Материалы'
RESOURCES_CMD = u'Ресурсы'
LEVELS_CMD = u'Уровни'
NEWS_CMD = u'Новости'
CHINESE_POD_CMD = 'Chinese Pod'
CONFIRM_CMD = u'Подтвердить'
CANCEL_CMD = u'Отменить'
GROUP1_CMD = u'Группа 1'
GROUP2_CMD = u'Группа 2'
ALL_CMD = u'Все'
USER_LIST_CMD = u'Пользователи'
GOOGLE_SHEET_CMD = u'Гуглшит'
SEND_CMD = u'Рассылка'
HELP_CMD = u'Помощь'
HOMEWORK_CMD = '/homework'
RESULTS_CMD = '/results'
GROUP_CHAT_CMD = '/group_chat'
TEACHER_CMD = '/teacher'
START_CMD = '/start'
STOP_CMD = '/stop'
HELLO_CMD = '/hello'
NEXT_CMD = '/next'
GROUP_CHAT_CMD = '/group_chat'
MAIN_KEYBOARD = u'{{"keyboard" : [["{}", "{}", "{}"], ["{}", "{}", "{}"]], "resize_keyboard" : true}}'.format(SCHEDULE_CMD, CARD_CMD, STUFF_CMD, NEWS_CMD, CHINESE_POD_CMD, HELP_CMD)
MAIN_KEYBOARD_ADMIN = u'{{"keyboard" : [["{}", "{}", "{}"], ["{}", "{}", "{}"], ["{}", "{}", "{}"]], "resize_keyboard" : true}}'.format(SCHEDULE_CMD, CARD_CMD, STUFF_CMD, NEWS_CMD, CHINESE_POD_CMD, HELP_CMD, USER_LIST_CMD, GOOGLE_SHEET_CMD, SEND_CMD)
HELP_TEXT = u"{} -- прислать расписание\n\
{} -- прислать реквизиты карты для оплаты\n\
{} -- ресурсы и материалы для уровней\n\
{} -- повторить последние новости (анонсы)\n\
{} -- доступ к Chinese Pod\n\
{} -- описание команд и советы".format(SCHEDULE_CMD, CARD_CMD, STUFF_CMD, NEWS_CMD, CHINESE_POD_CMD, HELP_CMD)
HELP_ADMIN_TEXT = HELP_TEXT + u"\n\
{} - список пользователей\n\
{} - ссылка на гуглшит\n\
{} - рассылки по разным группам".format(USER_LIST_CMD, GOOGLE_SHEET_CMD, SEND_CMD)
HELP_MORE_TEXT = u'Полезные советы:\n\
- Установите desktop приложение Telegram на ваш компьютер, чтобы сохранять файлы и работать с документами.\n\
- Для группового чата используйте в меню слева функцию “Mute notifications”, если хотите, чтобы оповещения о новых сообщениях не отвлекали вас.\n\
- По желанию в настройках установите аватарку :)\n\
\n\
Разработка бота: @DepecheBot'
MESSAGE_ALARM = "Аларм! Аларм!"
CHAT_ID_ALARM = 79031498
ADMIN_PASS = 'I am god'
GROUP1_CHAT_LINK = 'Нажмите, чтобы добавиться в групповой чат: https://telegram.me/joinchat/BLXsyj9Qyw345JsKEVBFNQ'
GROUP2_CHAT_LINK = 'Нажмите, чтобы добавиться в групповой чат: https://telegram.me/joinchat/BLXsyj95-Y2APYkG70_l7A'
NEWS_TEXT = "Пока новостей нет..."
RESULTS_TEXT = "Пока результатов нет"
HOMEWORK_TEXT = "Пока домашнего задания нет"
REGISTER_TEXT = 'Пожалуйста, введите выданное Вам кодовое слово, чтобы я понял, из какой Вы группы:'
GOOGLE_SHEET = 'https://docs.google.com/spreadsheets/d/1Lso2rRoop-UzzTloC1wEZM-G4g3Iwg-28LKgHY8ffP0'
TELEGRAM_MSG_CHANNEL = '#telegram-messages'



def main():
    global LAST_UPDATE_ID

    parser = argparse.ArgumentParser(description=BOT_DESCRIPTION)
    parser.add_argument("--logfile", type=str, default='log', help="Path to log file")
    parser.add_argument("--dbfile", type=str, default='proofspace.sqlite', help="Path to sqlite DB file")
    args = parser.parse_args()

    botDB.bind('sqlite', args.dbfile, create_db=True)
    botDB.generate_mapping(create_tables=True)

    # TODO: use it
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())

    telegram_token = open('.telegram_token').readline().strip()
    slack_token = open('.slack_token').readline().strip()
    bot = telegram.Bot(telegram_token)
    slackbot = SlackClient(slack_token)

    try:
        LAST_UPDATE_ID = bot.getUpdates()[-1].update_id
    except IndexError:
        LAST_UPDATE_ID = None

    while True:
        try:
            run(bot, args.logfile, slackbot)
        except telegram.TelegramError as error:
            print "TelegramError", error
            time.sleep(1)
        #except urllib2.URLError as error:
        #    print "URLError", error
        #    time.sleep(1)
        except:
            traceback.print_exc()
            try:
                bot.sendMessage(chat_id=CHAT_ID_ALARM, text=MESSAGE_ALARM)
            except:
                pass
            time.sleep(100) # 100 seconds


def log_update(update, logfile, slackbot, primary_id):
    message = update.message
    slack_text = u'Proof Space. {} {} ({}, GSid: {}): {{}}\n'.format(message.from_user.first_name,
                                                        message.from_user.last_name,
                                                        message.from_user.name,
                                                        primary_id)
    if message.left_chat_member:
        slack_text = slack_text.format('left bot chat')
    elif message.new_chat_member:
        slack_text = slack_text.format('joined bot chat')
    else:
        slack_text = slack_text.format(message.text)
    log_text = update.to_json().decode('unicode-escape').encode('utf-8') + '\n'

    slackbot.chat_post_message(TELEGRAM_MSG_CHANNEL, slack_text, as_user=True)
    with open(logfile, 'a') as log:
        log.write(log_text)


def update_chat_db(message):
    with db_session:
        chat = Chat.get(chat_id=message.chat.id)
        if chat == None:
            chat = Chat(chat_id=message.chat.id, user_id=message.from_user.id, open_date=datetime.now(), \
                        last_message_date=datetime.now(), username=message.from_user.username, \
                        first_name=message.from_user.first_name, last_name=message.from_user.last_name, \
                        silent_mode=False, deleted=False, group_id="nobody", state="REGISTER_STATE", \
                        realname="")
        else:
            chat.last_message_date = datetime.now()
            chat.username = message.from_user.username
            chat.first_name = message.from_user.first_name
            chat.last_name = message.from_user.last_name

        return chat


def send_broad(bot, text, group):
    with db_session:
        for chat in select(chat for chat in Chat if not (chat.silent_mode or chat.deleted) and \
                           (chat.group_id == group or group == "all")):
            try:
                #is_admin = 
                #reply_markup = MAIN_KEYBOARD_ADMIN if is_admin else MAIN_KEYBOARD
                bot.sendMessage(chat_id=chat.chat_id, text=text)#, reply_markup=reply_markup)
            except telegram.TelegramError as error:
                print "TelegramError", error


def forward_broad(bot, from_chat_id, message_id, group):
    with db_session:
        for chat in select(chat for chat in Chat if not (chat.silent_mode or chat.deleted) and \
                           (chat.group_id == group or group == "all")):
            try:
                #is_admin = 
                #reply_markup = MAIN_KEYBOARD_ADMIN if is_admin else MAIN_KEYBOARD
                #bot.sendMessage(chat_id=chat.chat_id, text=text)#, reply_markup=reply_markup)
                bot.forwardMessage(chat_id=chat.chat_id, from_chat_id=from_chat_id, message_id=message_id)
                chat.news = '{} {}'.format(from_chat_id, message_id)
            except telegram.TelegramError as error:
                print "TelegramError", error


def send_large_message(bot, chat_id, text):
    MAX_LINES = 100

    def grouper(iterable, n, fillvalue=None):
        "Collect data into fixed-length chunks or blocks"
        # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
        args = [iter(iterable)] * n
        return itertools.izip_longest(fillvalue=fillvalue, *args)

    lines = text.splitlines()
    for block in grouper(lines, MAX_LINES, ''):
        bot.sendMessage(chat_id=chat_id, text='\n'.join(block))


def print_userlist(bot, message):
    with db_session:
        chats_str = ''
        for chat in select(chat for chat in Chat):
            chats_str += u'{}. {} (@{}, {})'.format(chat.primary_id, chat.realname, \
                                                     chat.username, chat.group_id)
            if chat.silent_mode:
                chats_str += ' (silent mode)'
            if chat.deleted:
                chats_str += ' (deleted)'
            chats_str += '\n'

        try:
            send_large_message(bot, message.chat_id, chats_str)
        except telegram.TelegramError as error:
            print "TelegramError", error


        group1_str = u'Группа 1:\n'
        for chat in select(chat for chat in Chat if chat.group_id == "group1"):
            group1_str += u'{}. {} (@{})'.format(chat.primary_id, chat.realname, chat.username)

            if chat.silent_mode:
                group1_str += ' (silent mode)'
            if chat.deleted:
                group1_str += ' (deleted)'
            group1_str += '\n'

        try:
            send_large_message(bot, message.chat_id, group1_str)
        except telegram.TelegramError as error:
            print "TelegramError", error


        # group2_str = 'Group 2:\n'
        # for chat in select(chat for chat in Chat if chat.group_id == "group2"):
        #     group2_str += u'{}. {} (@{})'.format(chat.primary_id, chat.realname, chat.username)

        #     if chat.silent_mode:
        #         group2_str += ' (silent mode)'
        #     if chat.deleted:
        #         group2_str += ' (deleted)'
        #     group2_str += '\n'

        # try:
        #     send_large_message(bot, message.chat_id, group2_str)
        # except telegram.TelegramError as error:
        #    print "TelegramError", error



def send_message(bot, message):
    with db_session:
        cmd = text = ''
        primary_id = 0
        params = message.text.split(' ', 2)
        if len(params) > 0:
            cmd = params[0]
        if len(params) > 1:
            try:
                primary_id = int(params[1])
            except ValueError:
                bot.sendMessage(chat_id=message.chat_id, text='cannot find user')
                return False
        if len(params) > 2:
            text = params[2]
        if primary_id == 0:
            bot.sendMessage(chat_id=message.chat_id, text='cannot send message to empty user')
        elif len(text) == 0:
            bot.sendMessage(chat_id=message.chat_id, text='cannot send empty message')
        else:
            chat = Chat.get(primary_id=primary_id)
            if chat == None:
                bot.sendMessage(chat_id=message.chat_id, text='cannot find user')
            elif chat.deleted:
                bot.sendMessage(chat_id=message.chat_id, text='this user marked as deleted')
            else:
                bot.sendMessage(chat_id=chat.chat_id, text=text)


def get_schedule_message():
    DOC = "{}/export?format=tsv&id={}&gid={}".format(GOOGLE_SHEET, '1eBh9w0WRRJleBQd7eVHFKBQgc5V_w0TYymMkKHL6598', '0')
    CMD = "curl -s '{}' | sed -e 's/[[:space:]]$//g' | awk 'NF > 1 {{print }}'".format(DOC)
    return os.popen(CMD).read()


def get_news_message():
    DOC = "{}/export?format=tsv&id={}&gid={}".format(GOOGLE_SHEET, '1eBh9w0WRRJleBQd7eVHFKBQgc5V_w0TYymMkKHL6598', '1907552920')
    CMD = "curl -s '{}' | tail -1".format(DOC)
    return os.popen(CMD).read()


def run(bot, logfile, slackbot):
    global LAST_UPDATE_ID
    for update in bot.getUpdates(offset=LAST_UPDATE_ID, timeout=10):
        message = update.message

        chat = update_chat_db(message)
        primary_id, group_id, state, silent_mode, deleted, realname, news = \
            chat.primary_id, chat.group_id, chat.state, chat.silent_mode, chat.deleted, chat.realname, chat.news

        log_update(update, logfile, slackbot, primary_id)

        #automata_step(message, chat)

        reply_markup = MAIN_KEYBOARD_ADMIN if ((group_id == "admin") or (group_id == 'teacher')) else MAIN_KEYBOARD

        print(u"State: {}. Message: {}".format(state, message.text))

        if state.startswith("REGISTER_STATE"):
            if len(state.split()) == 1:
                reply_markup = u'{{"keyboard" : [["{}"]], "resize_keyboard" : true, "one_time_keyboard" : true}}'.format(CONFIRM_CMD)
                realname = u"{} {}".format(message.from_user.first_name, message.from_user.last_name)
                text = u'Ваше имя и фамилия в Телеграме: {}. Подтвердите его (нажмите или наберите "{}") или введите Вашe имя и фамилию для использования в этом боте:'.format(realname, CONFIRM_CMD)
                bot.sendMessage(chat_id=message.chat_id, text=text, reply_markup=reply_markup)
                state = "REGISTER_STATE password"
            elif len(state.split()) == 2:
                if message.text != CONFIRM_CMD:
                    realname = message.text
                bot.sendMessage(chat_id=message.chat_id, text=u"Ваше имя: {}".format(realname), reply_markup=telegram.ReplyKeyboardHide())

                #bot.sendMessage(chat_id=message.chat_id, text=REGISTER_TEXT)
                #state = "REGISTER_STATE password realname"

                bot.sendMessage(chat_id=message.chat_id, text=u'Вы в группе 1! Выберите команду:', reply_markup=reply_markup)
                state = "MAIN_STATE"
            elif len(state.split()) == 3:
                password = message.text
                if password == "umbrella":
                    group_id = "group1"
                    bot.sendMessage(chat_id=message.chat_id, text="Спасибо, вы в группе 1!", reply_markup=MAIN_KEYBOARD)
                    state = "MAIN_STATE"
                elif password == "butterfly":
                    group_id = "group2"
                    bot.sendMessage(chat_id=message.chat_id, text="Спасибо, вы в группе 2!", reply_markup=MAIN_KEYBOARD)
                    state = "MAIN_STATE"
                elif password == "god":
                    group_id = "teacher"
                    bot.sendMessage(chat_id=message.chat_id, text="Вы учитель!", reply_markup=MAIN_KEYBOARD_ADMIN)
                    state = "MAIN_STATE"
                elif password == "boss":
                    group_id = "admin"
                    bot.sendMessage(chat_id=message.chat_id, text="Вы администратор!", reply_markup=MAIN_KEYBOARD_ADMIN)
                    state = "MAIN_STATE"
                else:
                    bot.sendMessage(chat_id=message.chat_id, text="Кодовое слово мне неизвестно :(")
                    bot.sendMessage(chat_id=message.chat_id, text=REGISTER_TEXT)

        elif state == "MAIN_STATE":
            if message.left_chat_member != None:
                if message.left_chat_member.id == bot.getMe().id:
                    deleted = True
            elif message.new_chat_member != None:
                if message.new_chat_member.id == bot.getMe().id:
                    deleted = False
            elif message.text == HELP_CMD:
                    bot.sendMessage(chat_id=message.chat_id, \
                                    text=HELP_ADMIN_TEXT if ((group_id == "admin") or (group_id == 'teacher')) else HELP_TEXT)
                    bot.sendMessage(chat_id=message.chat_id, text=HELP_MORE_TEXT)
            # elif message.text == START_CMD:
            #     silent_mode = False
            #     deleted = False
            #     bot.sendMessage(chat_id=message.chat_id, text=MESSAGE_START, reply_markup=reply_markup)
            # elif message.text == STOP_CMD:
            #     silent_mode = True
            #    bot.sendMessage(chat_id=message.chat_id, text=MESSAGE_STOP, reply_markup=reply_markup)
            elif message.text == GROUP_CHAT_CMD:
                if group_id == 'group1':
                    bot.sendMessage(chat_id=message.chat_id, text=GROUP1_CHAT_LINK, reply_markup=reply_markup)
                elif group_id == 'group2':
                    bot.sendMessage(chat_id=message.chat_id, text=GROUP2_CHAT_LINK, reply_markup=reply_markup)
                elif group_id == 'admin' or group_id == 'teacher':
                    bot.sendMessage(chat_id=message.chat_id, text=GROUP1_CHAT_LINK, reply_markup=reply_markup)
                    bot.sendMessage(chat_id=message.chat_id, text=GROUP2_CHAT_LINK, reply_markup=reply_markup)
            elif message.text == ADMIN_PASS:
                bot.sendMessage(chat_id=message.chat_id, text=u'Вы администратор!', reply_markup=MAIN_KEYBOARD_ADMIN)
                group_id = 'admin'
            elif message.text == NEWS_CMD:
                #news_message = get_news_message()
                if news == '':
                    bot.sendMessage(chat_id=message.chat_id, text=u"Пока никаких новостей...", reply_markup=reply_markup)
                else:
                    from_chat_id, message_id = map(int, news.split())
                    try:
                        bot.forwardMessage(chat_id=message.chat_id, from_chat_id=from_chat_id, message_id=message_id)
                    except telegram.TelegramError as error:
                        print "TelegramError", error
            elif message.text == TEACHER_CMD:
                bot.sendMessage(chat_id=message.chat_id, text=TEACHER_TEXT, reply_markup=reply_markup)
            elif message.text == HOMEWORK_CMD:
                bot.sendMessage(chat_id=message.chat_id, text=HOMEWORK_TEXT, reply_markup=reply_markup)
            elif message.text == RESULTS_CMD:
                bot.sendMessage(chat_id=message.chat_id, text=RESULTS_TEXT, reply_markup=reply_markup)
            elif message.text == CARD_CMD:
                bot.sendMessage(chat_id=message.chat_id, text=u'Номер карты: 4276 5500 6960 1089, получатель: Климовская Динара Омирхановна. Сбербанк.\nПожалуйста, скиньте скрин платежа Яне (@yasaukova), как отправите перевод)', reply_markup=reply_markup)
            elif message.text == CHINESE_POD_CMD:
                bot.sendMessage(chat_id=message.chat_id, text=u'Доступ к Chinese Pod:\nlogin - mousebanastro@gmail.com\npassword - lagou', reply_markup=reply_markup)
            elif message.text == STUFF_CMD:
                #bot.sendMessage(chat_id=message.chat_id, text=u'Пимслер (https://yadi.sk/d/7E_5aVZLt5Nwf)', reply_markup=reply_markup)
                #bot.sendMessage(chat_id=message.chat_id, text=u'Видео: https://yadi.sk/d/UZQt40fKtDLpW -- уровень 1\nhttps://yadi.sk/d/NvR0AXDhsM7iK -- уровень 2', reply_markup=reply_markup)
                #bot.sendMessage(chat_id=message.chat_id, text=u'Ресурсы для обучения: busuu.com. Крутые приложения: memsrise, pleco, trainchinese', reply_markup=reply_markup)
                #bot.sendMessage(chat_id=message.chat_id, text=u'Книга по ключам (https://vk.com/doc326978802_437453577?hash=0a34fc79dbdf96e3b8&dl=09475a5fd4ad299d57)', reply_markup=reply_markup)
                bot.sendMessage(chat_id=message.chat_id, text=u'Пимслер (https://yadi.sk/d/7E_5aVZLt5Nwf)\n\
Видео: \n  https://yadi.sk/d/UZQt40fKtDLpW -- уровень 1\n  https://yadi.sk/d/NvR0AXDhsM7iK -- уровень 2\n\
Ресурсы для обучения: busuu.com. Крутые приложения: memsrise, pleco, trainchinese\n\
Книга по ключам (https://vk.com/doc326978802_437453577?hash=0a34fc79dbdf96e3b8&dl=09475a5fd4ad299d57)', reply_markup=reply_markup)
            elif message.text == RESOURCES_CMD:
                bot.sendMessage(chat_id=message.chat_id, text=u'Ресурсы для обучения: busuu.com. Крутые приложения: memsrise, pleco, trainchinese', reply_markup=reply_markup)
            elif message.text == LEVELS_CMD:
                bot.sendMessage(chat_id=message.chat_id, text=u'https://yadi.sk/d/UZQt40fKtDLpW -- видео уровень 1\nhttps://yadi.sk/d/NvR0AXDhsM7iK -- видео уровень 2', reply_markup=reply_markup)
            elif message.text == SCHEDULE_CMD:
                #bot.sendMessage(chat_id=message.chat_id, text="Расписание не установлено", reply_markup=reply_markup)
                #if group_id == "group1":
                #    bot.sendMessage(chat_id=message.chat_id, text="Расписание не установлено", reply_markup=reply_markup)
                #elif group_id == "group2":
                #    bot.sendMessage(chat_id=message.chat_id, text="Среда, с 19:30 до 20:00", reply_markup=reply_markup)
                #else:
                #    schedule_message = get_schedule_message()
                #    bot.sendMessage(chat_id=message.chat_id, text=schedule_message, reply_markup=reply_markup)
                schedule_message = get_schedule_message()
                bot.sendMessage(chat_id=message.chat_id, text=schedule_message, reply_markup=reply_markup)

            elif (group_id == "admin" or group_id == "teacher") and message.text == SEND_CMD:
                state = "SEND_STATE"
                reply_markup = u'{{"keyboard" : [["{}", "{}"]], "resize_keyboard" : true}}'.format(NEWS_CMD, CANCEL_CMD)
                bot.sendMessage(chat_id=message.chat_id, text=u"Отослать новость?", reply_markup=reply_markup)
            elif ((group_id == "admin") or (group_id == 'teacher')) and message.text == USER_LIST_CMD:
                print_userlist(bot, message)
            elif ((group_id == "admin") or (group_id == 'teacher')) and message.text == GOOGLE_SHEET_CMD:
                bot.sendMessage(chat_id=message.chat_id, text=u'Ссылка на гуглшит: {}'.format(GOOGLE_SHEET), reply_markup=reply_markup)
            else:
                pass

        elif state.startswith("SEND_STATE"):
            if message.text == CANCEL_CMD:
                bot.sendMessage(chat_id=message.chat_id, text=u"Рассылка отменена", reply_markup=reply_markup)
                state = "MAIN_STATE"
            elif len(state.split()) == 1:
                if message.text == NEWS_CMD:
                    state += " news"
                    reply_markup = u'{{"keyboard" : [["{}", "{}", "{}"]], "resize_keyboard" : true}}'.format(GROUP1_CMD, ALL_CMD, CANCEL_CMD)
                    bot.sendMessage(chat_id=message.chat_id, text=u"Выберите группу для рассылки:", reply_markup=reply_markup)
                elif message.text == HOMEWORK_CMD:
                    state += " homework"
                    reply_markup = u'{{"keyboard" : [["{}", "{}", "{}"]], "resize_keyboard" : true}}'.format(GROUP1_CMD, ALL_CMD, CANCEL_CMD)
                    bot.sendMessage(chat_id=message.chat_id, text=u"Выберите группу для рассылки:", reply_markup=reply_markup)
                else:
                    reply_markup = u'{{"keyboard" : [["{}", "{}"]], "resize_keyboard" : true}}'.format(NEWS_CMD, CANCEL_CMD)
                    bot.sendMessage(chat_id=message.chat_id, text=u'Отослать новость', reply_markup=reply_markup)
            elif len(state.split()) == 2:
                if message.text == GROUP1_CMD:
                    state += " group1"
                    reply_markup = u'{{"keyboard" : [["{}"]], "resize_keyboard" : true}}'.format(CANCEL_CMD)
                    bot.sendMessage(chat_id=message.chat_id, text=u"Введите сообщение для рассылки (или файл/картинку):", reply_markup=reply_markup)
                elif message.text == GROUP2_CMD:
                    state += " group2"
                    reply_markup = u'{{"keyboard" : [["{}"]], "resize_keyboard" : true}}'.format(CANCEL_CMD)
                    bot.sendMessage(chat_id=message.chat_id, text=u"Введите сообщение для рассылки (или файл/картинку):", reply_markup=reply_markup)
                elif message.text == ALL_CMD:
                    state += " all"
                    reply_markup = u'{{"keyboard" : [["{}"]], "resize_keyboard" : true}}'.format(CANCEL_CMD)
                    bot.sendMessage(chat_id=message.chat_id, text=u"Введите сообщение для рассылки (или файл/картинку):", reply_markup=reply_markup)
                else:
                    reply_markup = u'{{"keyboard" : [["{}", "{}", "{}"]], "resize_keyboard" : true}}'.format(GROUP1_CMD, ALL_CMD, CANCEL_CMD)
                    bot.sendMessage(chat_id=message.chat_id, text=u"Выберите группу для рассылки:", reply_markup=reply_markup)
            elif len(state.split()) == 3:
                state += " " + str(message.message_id)
                reply_markup = u'{{"keyboard" : [["{}", "{}"]], "resize_keyboard" : true}}'.format(CONFIRM_CMD, CANCEL_CMD)
                bot.sendMessage(chat_id=message.chat_id, text=u"Подтвердите отправку:", reply_markup=reply_markup)
            elif len(state.split()) == 4:
                if message.text == CONFIRM_CMD:
                    _, _, group, message_id = state.split()
                    forward_broad(bot, from_chat_id=message.chat_id, message_id=message_id, group=group)
                    # Update news after broadcasting
                    with db_session:
                        chat = Chat.get(chat_id=message.chat.id)
                        news = chat.news
                    bot.sendMessage(chat_id=message.chat_id, text=u"Отправлено!", reply_markup=reply_markup)
                    state = "MAIN_STATE"
                else:
                    reply_markup = u'{"keyboard" : [["{}", "{}"]], "resize_keyboard" : true}'.format(CONFIRM_CMD, CANCEL_CMD)
                    bot.sendMessage(chat_id=message.chat_id, text="Подтвердите отправку:", reply_markup=reply_markup)


        elif state.startswith('STUFF_STATE'):
            if message.text == u'':
                pass

        with db_session:
            chat = Chat.get(chat_id=message.chat.id)
            chat.primary_id, chat.group_id, chat.state, chat.silent_mode, chat.deleted, chat.realname, chat.news = \
                primary_id, group_id, state, silent_mode, deleted, realname, news

        LAST_UPDATE_ID = update.update_id + 1



if __name__ == '__main__':
    main()
