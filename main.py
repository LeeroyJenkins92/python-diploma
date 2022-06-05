import telebot
import telegram
from telegram import InputMediaPhoto
from decouple import config
from collections import defaultdict
import sqlite3
import requests
import json
import more_itertools

conn = sqlite3.connect('user.db', check_same_thread=False)
cursor = conn.cursor()
bot = telebot.TeleBot(config("TOKEN"))
robot = telegram.Bot(config("TOKEN"))
media_group = []
temp_db = defaultdict(dict)
sort_info = str

headers = {
    'x-rapidapi-host': "hotels4.p.rapidapi.com",
    'x-rapidapi-key': config("KEY")
}


def req_cities(my_city):
    url = "https://hotels4.p.rapidapi.com/locations/v2/search"

    querystring = {"query": my_city, "locale": "en_US", "currency": "USD"}

    response = requests.request("GET", url, headers=headers, params=querystring)
    req_cities_db = json.loads(response.text)
    return req_cities_db


def req_hotels(my_city):
    url = "https://hotels4.p.rapidapi.com/properties/list"

    querystring = {"destinationId": city_id_getter(my_city), "pageNumber": "1", "pageSize": "50", "checkIn": "2020-01-08",
                   "checkOut": "2020-01-15", "adults1": "1", "sortOrder": "PRICE", "locale": "en_US", "currency": "USD"}

    response = requests.request("GET", url, headers=headers, params=querystring)
    req_hotels_db = json.loads(response.text)
    return req_hotels_db


def req_pics(hotel_idd, pcs_cnt):
    url = "https://hotels4.p.rapidapi.com/properties/get-hotel-photos"
    lst = []
    count = pcs_cnt
    querystring = {"id": str(hotel_idd)}
    response = requests.request("GET", url, headers=headers, params=querystring)
    req_pics_db = json.loads(response.text)
    photo_lib = req_pics_db.get('hotelImages')
    for each in photo_lib:
        lst.append(each.get("baseUrl").replace("{size}", "b"))
    total_count = len(lst)
    total_count -= count
    del lst[-total_count:]
    return lst


def db_table_val(user_id: int, user_name: str, user_surname: str, username: str):
    cursor.execute('INSERT INTO some_table (user_id, user_name, user_surname, username) VALUES (?, ?, ?, ?)',
                   (user_id, user_name, user_surname, username))
    conn.commit()


def user_check_query(my_id):
    useful_id = cursor.execute(f"SELECT username FROM some_table WHERE user_id = {my_id}")
    result = useful_id.fetchone()
    return result[0]


def find_hotels(my_city):
    hotels_db = dict()
    hotels_lst = req_hotels(my_city).get("data").get("body").get("searchResults").get("results")
    for each in hotels_lst:
        name = each.get('name')
        hotel_id = each.get('id')
        price = next(iter(each.get('ratePlan').get("price").values()))
        distance = each.get("landmarks")[0].get("distance").split()[0]
        hotels_db.update({name: [str(price), hotel_id, distance]})
    return hotels_db


def cheapest_hotels(my_city):
    cheapest_hotels_db = dict(sorted(find_hotels(my_city).items(), key=lambda item: item[1]))
    return cheapest_hotels_db


def richest_hotels(my_city):
    richest_hotels_db = dict(reversed(list(find_hotels(my_city).items())))
    return richest_hotels_db


def best_hotels(my_city, my_db):
    best_hotels_db = dict()
    for key, value in sorted(find_hotels(my_city).items(), key=lambda x: x[1][2]):
        if float(my_db.get("MilesRange")[0]) <= float(value[2]) <= float(my_db.get("MilesRange")[1]) and \
                float(my_db.get("PriceRange")[0]) <= float(value[0][1:]) <= float(my_db.get("PriceRange")[1]):
            best_hotels_db.update({key: value})
    return best_hotels_db


def city_id_getter(my_city):
    city_num = req_cities(my_city).get("suggestions")[0].get("entities")[0].get("destinationId")
    return city_num


@bot.message_handler(commands=["start"])
def start(message):
    # bot.send_message(message.chat.id, 'Я на связи. Напиши мне что-нибудь :)')
    bot.send_message(message.from_user.id, f'Привет! {message.from_user.username}')
    us_id = message.from_user.id
    us_name = message.from_user.first_name
    us_sname = message.from_user.last_name
    username = message.from_user.username
    db_table_val(user_id=us_id, user_name=us_name, user_surname=us_sname, username=username)


@bot.message_handler(commands=["lowprice", "highprice", "bestdeal"])
def hello(message):
    temp_db[user_check_query(message.chat.id)]["CMD"] = message.text
    if message.text == "/lowprice":
        msg = bot.reply_to(message, """\
        Выведем отели с более низкой стоимостью..
        Введите город:
        """)
        bot.register_next_step_handler(msg, city_getter)
    elif message.text == "/highprice":
        msg = bot.reply_to(message, """\
        Выведем отели с более высокой стоимостью..
        Введите город:
        """)
        bot.register_next_step_handler(msg, city_getter)
    elif message.text == "/bestdeal":
        msg = bot.reply_to(message, """\
        Выведем отели с наилучшим предложением..
        Введите желаемый диапазон расстояний (в милях) удаленности отеля от центра (через дефис) по возрастанию:
        пример: 3-11
        """)
        bot.register_next_step_handler(msg, best_deal_miles_getter)


def best_deal_miles_getter(message):
    miles_range = message.text.lower().split("-")
    temp_db[user_check_query(message.chat.id)]["MilesRange"] = miles_range
    bot.send_message(message.from_user.id, 'Введите диапазон цен:')
    bot.register_next_step_handler(message, best_deal_price_getter)


def best_deal_price_getter(message):
    price_range = message.text.lower().split("-")
    temp_db[user_check_query(message.chat.id)]["PriceRange"] = price_range
    bot.send_message(message.from_user.id, 'Введите город:')
    bot.register_next_step_handler(message, city_getter)


def city_getter(message):
    temp_db[user_check_query(message.chat.id)]["ID"] = message.chat.id
    bot.send_message(message.from_user.id, 'Введите кол-во отелей')
    city = message.text.lower()
    temp_db[user_check_query(message.chat.id)]["City"] = city
    city_id_getter(city)
    bot.register_next_step_handler(message, hotel_count_getter)


def hotel_count_getter(message):
    bot.send_message(message.from_user.id, 'Нужны ли фотки отелей (Да/Нет)')
    hotel_count = message.text.lower()
    temp_db[user_check_query(message.chat.id)]["HotelCount"] = int(hotel_count)
    bot.register_next_step_handler(message, picture_getter)


def picture_getter(message):
    pic_answer = message.text.lower()
    if pic_answer == "да":
        temp_db[user_check_query(message.chat.id)]["IfPics"] = True
        bot.send_message(message.from_user.id, 'Сколько нужно фоток?')
        bot.register_next_step_handler(message, picture_count_getter)
    else:
        temp_db[user_check_query(message.chat.id)]["IfPics"] = False
        output(message)


def picture_count_getter(message):
    pic_count = message.text.lower()
    temp_db[user_check_query(message.chat.id)]["PicsCount"] = int(pic_count)
    output(message)


def output(message):
    my_db = temp_db.get(user_check_query(message.chat.id))
    bot.send_message(my_db.get("ID"), 'Вот что удалось найти по Вашему запросу...: ')
    bot.send_message(my_db.get("ID"), f'Ваш город для поиска: {my_db.get("City")}')
    if my_db.get("CMD") == "/lowprice":
        first_n = more_itertools.take(my_db.get("HotelCount"), cheapest_hotels(my_db.get("City")).items())
    elif my_db.get("CMD") == "/highprice":
        first_n = more_itertools.take(my_db.get("HotelCount"), richest_hotels(my_db.get("City")).items())
    elif my_db.get("CMD") == "/bestdeal":
        first_n = more_itertools.take(my_db.get("HotelCount"), best_hotels(my_db.get("City"), my_db).items())
    for each in first_n:
        bot.send_message(my_db.get("ID"), f'Ваш отель: {each[0]} со стоимостью {each[1][0]}')
        if my_db.get("IfPics"):
            for element in req_pics(each[1][1], my_db.get("PicsCount")):
                media_group.append(InputMediaPhoto(element, caption=each[0]))
            robot.send_media_group(chat_id=message.chat.id, media=media_group)
            media_group.clear()


# Запускаем бота
bot.polling(none_stop=True, interval=0)
