import config
import telebot
from telebot import types
import requests
from bs4 import BeautifulSoup
import time
import eventlet
import logging
from time import sleep
import json
from telebot.types import InputMediaPhoto
import pymongo
from pymongo import MongoClient

mongo_user = config.mongo_user
mongo_pass = config.mongo_pass
mongo_db = config.mongo_db
link = 'mongodb+srv://{}:{}@cluster0-e2dix.mongodb.net/{}?retryWrites=true&w=majority'.format("Leonid", mongo_pass, mongo_db)

client = MongoClient(link)
db = client.telegrambot
chat_id_hashtags = db.chatid_hashtags
hashtag_chat_ids = db.hashtags_chatid
chat_id_status = db.chat_id_status
posts = db.posts
global_post = 0

bot = telebot.TeleBot(config.token)
site = 'https://vk.com/spbu_advert'
URL_VK = 'https://api.vk.com/method/wall.get?domain=spbu_advert&count=10&filter=owner&access_token=566214435662144356621443e5560a2ea255662566214430a2a6f6205658190bc5351eb&v=5.100'

FILENAME_VK = 'last_known_id.txt'
BASE_POST_URL = 'https://m.vk.com/wall-50260527_21339_'
CHANNEL_NAME = '@AnnouncementsPUNK'

def get_html(site):
    r = requests.get(site)
    return r.text

def get_page_data(html):
    soup = BeautifulSoup(html, 'lxml')
    
    wall = soup.findAll('div', class_='wall_item')

    return str(wall)

def get_data():
    timeout = eventlet.Timeout(10)
    try:
        feed = requests.get(URL_VK)
        return feed.json()
    except eventlet.timeout.Timeout:
        logging.warning('Got Timeout while retrieving VK JSON data. Cancelling...')
        return None
    finally:
        timeout.cancel()

def save_last_index(index):
    index = str(index)
    with open(FILENAME_VK, 'wt') as file:
        try:
            file.write(index)
            logging.info('New last_id (VK) is {!s}'.format(index))
        except:
            file.write(index)
            logging.info('New last_id (VK) is {!s}'.format(index))
 

def send_new_posts(items, last_id):
    items = items[::-1]
    print(len(items))
    for item in items:
        if int(item['id']) <= last_id:
            continue
        #link = '{!s}{!s}'.format(BASE_POST_URL, item['id'])
        print(item['text'][:50])
        hashtags = []
        msg = ''
        text = item['text']
        i = 0
        while i < len(text):
            if text[i] == '#':
                i += 1
                tag = ''
                while i < len(text) and not(text[i] == '\n' or text[i] == ' '):
                    if text[i] >= 'а' and text[i] <= 'я' or text [i] == '_':
                        tag += text[i]
                        i += 1
                    else:
                        while i < len(text) and not (text[i] == '\n' or text[i] == ' '):
                            i += 1
                        break
                while i < len(text) and (text[i] == ' ' or text[i] == '\n'):
                    i += 1
                hashtags.append(tag)
                
                if(i < len(text)):
                    print('m' + text[i-1] + 't' + text[i] + tag)
            else:
                msg += text[i]
                i += 1

        i = len(msg) - 1
        if(i <= 0):
            continue
        while msg[i] == '\n' or msg[i] == ' ':
            msg = msg[:-1]
            i -= 1
        #print(msg)
        msg += '\n\n'
        for i in hashtags:
            msg += '#' + i + '\n'
        #print(item.keys())
        if 'signer_id' in item.keys():
            msg += '\nhttps://vk.com/id' + str(item['signer_id'])
        #print(msg)
        mes_in_chat = bot.send_message(CHANNEL_NAME, msg)
        #print(mes_in_chat)
        
        mes_id = mes_in_chat.message_id
        print(mes_id)
        for tag in hashtags:
            chat_ids = hashtag_chat_ids.find_one({'tag': tag})
            if chat_ids == None:
                continue
            chat_ids = chat_ids['chat_ids']
            for chat_id in chat_ids:
                bot.forward_message(chat_id, -1001151046874, mes_id)

        time.sleep(1)
        
        #print("OKKK")
        if not 'attachments' in item.keys():
            print("not attachmenets")
            save_last_index(item['id'])
            continue

        media = item['attachments']
        photos = []
        one_url = ''
        for it in media:
            if it['type'] == 'photo':
                sizes = it['photo']['sizes']
                max_height = 0
                max_url = ''
                for photo in sizes:
                    height = int(photo['height'])
                    url = photo['url']
                    if height > max_height:
                        max_height = height
                        max_url = url
                one_url = max_url
                photos.append(InputMediaPhoto(max_url))
        print(photos)
        if len(photos) > 1:
            bot.send_media_group(CHANNEL_NAME, photos)
        elif len(photos) == 1:
            bot.send_photo(CHANNEL_NAME, one_url)
        save_last_index(item['id'])
        time.sleep(5)
    return

def check_new_posts_vk():
    logging.info('[VK] Started scanning for new posts')
    with open(FILENAME_VK, 'rt') as file:
        last_id = int(file.read())
        if last_id is None:
            logging.error('Could not read from storage. Skipped iteration.')
            return
        logging.info('Last ID (VK) = {!s}'.format(last_id))
    try:
        feed = get_data()
        
        if feed is not None:
            entries = feed['response']['items']
            try:
                tmp = entries[0]['is_pinned']
                send_new_posts(entries[1:], last_id)
            except KeyError:
                send_new_posts(entries, last_id)
    except Exception as ex:
        logging.error('Exception of type {!s} in check_new_post(): {!s}'.format(type(ex).__name__, str(ex)))
        pass
    logging.info('[VK] Finished scanning')
    return


@bot.message_handler(commands=['start'])
def start(msg):
    chat_id = msg.chat.id
    bot.send_message(chat_id, "Для бота доступны следующие команды:\n\
/add_tags - добавить тэги\n\
/del_tags - удалить теги\n\
/show_tags - показать мои теги\n\
/new_post - создать новый пост\n")


@bot.message_handler(commands=['add_tags'])
def _add_tags(msg):
    chat_id = msg.chat.id
    str_chat_id = str(chat_id)
    chat_id_status.delete_one({'chat_id': str_chat_id})
    chat_id_status.insert_one({'chat_id': str_chat_id, 'status': 'add'})
    bot.send_message(chat_id, "В следующем сообщении отправьте мне список тегов, на которые хотите подписаться. \
Формат сообщения должен быть таким:\ntag1 tag2 tag3")

def add_tags(msg):
    chat_id = msg.chat.id
    str_chat_id = str(chat_id)
    new_tags = msg.text.split(' ')

    old_tags = chat_id_hashtags.find_one({'chat_id': str_chat_id})
    chat_id_hashtags.delete_one({'chat_id': str_chat_id})

    if old_tags != None:
        old_tags = old_tags['tags']
        old_tags.extend(new_tags)
    else:
        old_tags = new_tags

    chat_id_hashtags.insert_one({'chat_id': str_chat_id, 'tags': list(set(old_tags))})
    
    for tag in new_tags:
        tag_chat_ids = hashtag_chat_ids.find_one({'tag': tag})
        hashtag_chat_ids.delete_one({'tag': tag})

        if tag_chat_ids != None:
            tag_chat_ids = tag_chat_ids['chat_ids']
            tag_chat_ids.append(str_chat_id)
        else:
            tag_chat_ids = [str_chat_id]

        hashtag_chat_ids.insert_one({'tag': tag, 'chat_ids': list(set(tag_chat_ids))})

    chat_id_status.delete_one({'chat_id': str_chat_id})
        

@bot.message_handler(commands=['del_tags'])
def _del_tags(msg):
    chat_id = msg.chat.id
    str_chat_id = str(chat_id)
    chat_id_status.delete_one({'chat_id': str_chat_id})
    chat_id_status.insert_one({'chat_id': str_chat_id, 'status': 'del'})
    bot.send_message(chat_id, "В следующем сообщении отправьте мне список тегов, от которых хотите отписаться. \
Формат сообщения должен быть таким:\ntag1 tag2 tag3")

def del_tags(msg):
    chat_id = msg.chat.id
    str_chat_id = str(chat_id)
    new_tags = msg.text.split(' ')

    old_tags = chat_id_hashtags.find_one({'chat_id': str_chat_id})
    chat_id_hashtags.delete_one({'chat_id': str_chat_id})
    
    if old_tags != None:
        old_tags = list(old_tags['tags'])
        old_tags = list(set(old_tags).difference(set(new_tags)))
        
        if len(old_tags) > 0:
            chat_id_hashtags.insert_one({'chat_id': str_chat_id, 'tags': old_tags})
    
    for tag in new_tags:
        tag_chat_ids = hashtag_chat_ids.find_one({'tag': tag})
        hashtag_chat_ids.delete_one({'tag': tag})

        if tag_chat_ids != None:
            tag_chat_ids = tag_chat_ids['chat_ids']
            if str_chat_id in tag_chat_ids:
                tag_chat_ids.remove(str_chat_id)
            
            if len(tag_chat_ids) > 0:
                hashtag_chat_ids.insert_one({'tag': tag, 'chat_ids': tag_chat_ids})

    chat_id_status.delete_one({'chat_id': str_chat_id})


@bot.message_handler(commands=['show_tags'])
def _show_tags(msg):
    chat_id = msg.chat.id
    str_chat_id = str(chat_id)
    tags = chat_id_hashtags.find_one({'chat_id': str_chat_id})
    if tags == None:
        bot.send_message(chat_id, "У Вас еще нет тегов. Чтобы их добавить нажмите /add_tags")
    else:
        tags = tags['tags']
        bot.send_message(chat_id, "Вы подписаны на следующие теги:\n" + ' '.join(tags))

 
@bot.message_handler(commands=['new_post'])
def _new_post(msg):
    chat_id = msg.chat.id
    str_chat_id = str(chat_id)
    chat_id_status.delete_one({'chat_id': str_chat_id})
    chat_id_status.insert_one({'chat_id': str_chat_id, 'status': 'new_post'})
    bot.send_message(chat_id, "Отправьте мне текст Вашего обьявления.\n\
В конце сообщения можно указать список хэштегов - с их помощь продать\купить тавар можно быстрее.\n\
Каждый хэштег должен начинаться со знака #.\n\
Все хэштеги должны быть разделены пробелом.")
 

def new_post(msg):
    chat_id = msg.chat.id
    str_chat_id = str(chat_id)

    posts.delete_one({'chat_id': str_chat_id})
    posts.insert_one({'chat_id': str_chat_id, 'username': msg.from_user.username,\
        'text': msg.text + '\n\n' + '@' + msg.from_user.username, 'status': 'writing', 'photos': []})
    bot.send_message(chat_id, "Отлично! Теперь пришлите мне фотографии.\
После загрузки последней фотографии отправьте любое сообщение - чтобы Я понял, что Вы закончили.")

    chat_id_status.delete_one({'chat_id': str_chat_id})
    chat_id_status.insert_one({'chat_id': str_chat_id, 'status': 'add_photo'})


@bot.message_handler(content_types=["photo"])
def add_photos(msg):
    chat_id = msg.chat.id
    str_chat_id = str(chat_id)
    
    post = posts.find_one({'chat_id': str_chat_id})
    posts.delete_one({'chat_id': str_chat_id})

    mid = msg.media_group_id
    photos = msg.photo
    file_id = 0
    input_media = []
    for PhotoSize in photos:
        file_id = PhotoSize.file_id
        input_media.append(InputMediaPhoto(file_id))
        post['photos'].append(file_id)
        break
    posts.insert_one(post)


def send_global_post():
    global global_post
    str_chat_id = global_post['chat_id']
    chat_id = int(str_chat_id)

    keyboard = types.InlineKeyboardMarkup()
    callback_button = types.InlineKeyboardButton(text="Активное", callback_data="active")
    keyboard.add(callback_button)
    
    msg = bot.send_message(CHANNEL_NAME, global_post['text'], reply_markup=keyboard)
   
    posts.delete_one(global_post)
    global_post['status'] = 'active'
    global_post['mes_id'] = msg.message_id
    posts.insert_one(global_post)

    photos = global_post['photos']
    if len(photos) == 1:
        bot.send_photo(CHANNEL_NAME, photos[0])
    elif len(photos) > 1:
        photos = photos[:10]
        photos = [InputMediaPhoto(photo) for photo in photos]
        bot.send_media_group(CHANNEL_NAME, photos)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    username = call.from_user.username

    if call.message:
        msg = call.message
        post = posts.find_one({'mes_id': msg.message_id})

        if call.data == 'active' and post != None and post['username'] == username:
            
            keyboard = types.InlineKeyboardMarkup()
            callback_button = types.InlineKeyboardButton(text="Неактивное", callback_data="notactive")
            keyboard.add(callback_button)
            
            bot.edit_message_reply_markup(chat_id=CHANNEL_NAME, message_id=msg.message_id, reply_markup=keyboard)
            posts.delete_one({'mes_id': msg.message_id})
            print("delete suc")

@bot.message_handler(content_types=["text"])
def main_logic(msg):
    global global_post
    chat_id = msg.chat.id
    str_chat_id = str(chat_id)

    username = msg.from_user.username
    if username == 'romanychev':
        if msg.text == 'size':
            bot.send_message(chat_id, posts.find().count())
            return
        elif msg.text == 'get':
            global_post = posts.find_one({'status': 'checking'})
            
            if global_post == None:
                bot.send_message(chat_id, "Постов для проверки необнаружено")
                return

            bot.send_message(chat_id, global_post['text'])
            photos = global_post['photos']
            if len(photos) == 1:
                bot.send_photo(chat_id, photos[0])
            elif len(photos) > 1:
                photos = photos[:10]
                photos = [InputMediaPhoto(photo) for photo in photos]
                bot.send_media_group(chat_id, photos)
            return
        elif msg.text == 'ok':
            send_global_post()
            posts.update_one(global_post, {'$set': {'status': 'active'}})
            return
        

    status = chat_id_status.find_one({'chat_id': str_chat_id})
    if status == None:
        bot.send_message(chat_id, "Начать любое заимодействие с ботом можно через команды.\n\
Список команд доступен через команду \start")
        return

    status = status['status']
    print(status)

    if status == 'add':
        add_tags(msg)
    elif status == 'del':
        del_tags(msg)
    elif status == 'new_post':
        new_post(msg)
    elif status == 'add_photo':
        posts.update_one({'chat_id': str_chat_id}, {'$set':{'status': 'checking'}})
        chat_id_status.delete_one({'chat_id': str_chat_id})


def proccess_polling():
    print("process func")
    global bot
    bot.polling(none_stop=True)
    print("process end")

def process_while():
    SINGLE_RUN = 0
    logging.getLogger('requests').setLevel(logging.CRITICAL)
    logging.basicConfig(format='[%(asctime)s] %(filename)s:%(lineno)d %(levelname)s - %(message)s', level=logging.INFO, filename='bot_log.log', datefmt='%d.%m.%Y %H:%M:%S')
    if not SINGLE_RUN:
        while True:
            print("news")
            check_new_posts_vk()
            logging.info('[App] Script went to sleep.')
            time.sleep(60*5)
    else:
        check_new_posts_vk()
    logging.info('[App] Script exited.\n')


from multiprocessing import Process


if __name__ == '__main__':
    #proc = Process(target=proccess_polling)
    #proc.start()
    #while True:
    try:
        proc2 = Process(target=process_while)
        proc2.start()

        bot.polling(none_stop=True)
    except Exception as e:
        print(e.__class__)
        print("not ok") 
    
    print(end)
