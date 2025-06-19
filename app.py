import math

import openai
import requests
from flask import *
import File
from PIL import Image
import io
from openai import OpenAI
import base64
import json
from flask_mysqldb import MySQL
import MySQLdb.cursors

app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'mydatabase'

API_KEY = ""
openai.api_key = API_KEY

bot_personality = "You are a helpful assistant."
bot_prompt = "Find all the book titles in this image. For each book title, use the following format. Brackets represent what you replace, dont print out the brackets: %[Book Title]%. If no book title is found use the following format: %NONE%. Dont number the books."

@app.route("/")
def index():
    print("libraryObj")
    return render_template("index.html")

@app.route("/Library")
def library():
    return render_template("library.html", libraries=grab_json_data())

@app.route("/Books")
def book():
    return render_template("book.html", libraries=grab_json_data())

@app.route("/Photo", methods=['POST', 'GET'])
def photo():
    if request.method == 'POST':

        latitude = float(request.form.get("latitude"))
        longitude = float(request.form.get("longitude"))
        libraryForm = request.form.get("Library")
        file = request.files.get('PhotoDrop')
        image = Image.open(file.stream)
        image_path = "temp_uploaded_image.png"
        image.save(image_path)
        response = chatbot(image_path)
        books = response.choices[0].message.content

        books = parse_data(books)

        books_json = json.dumps(books)

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT library_name, books_json, latitude, longitude FROM libraries")
        result = cursor.fetchall()

        dist_new_library = 0.001
        i = 0
        current_i = 0
        min_dist = math.inf
        for row in result:
            long = float(row['longitude'])
            lat = float(row['latitude'])
            dist = math.sqrt((long - longitude) ** 2 + (lat - latitude) ** 2)
            if dist < min_dist:
                current_i = i
                min_dist = dist
            i += 1

        if min_dist < dist_new_library:
            libraryForm = result[current_i]['library_name']

        cursor.close()

        cursor = mysql.connection.cursor()

        cursor.execute("SELECT * FROM libraries WHERE library_name = %s", (libraryForm,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE libraries SET books_json = %s, latitude = %s, longitude = %s WHERE library_name = %s", (books_json, latitude, longitude, libraryForm))
        else:
            cursor.execute(
                "INSERT INTO libraries (library_name, books_json, latitude, longitude) VALUES (%s, %s, %s, %s)", (libraryForm, books_json, latitude, longitude))
        mysql.connection.commit()
        cursor.close()

        print(books)

    return render_template("photo.html")

def chatbot(img):
    with open(img, "rb") as image_file:
        image_bytes = image_file.read()
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
    messages = [{"role": "system", "content" : bot_personality}]
    messages.append(
        {"role" : "user", "content" : [{"type" : "text", "text" : bot_prompt}, {"type" : "image_url", "image_url" : {"url" : f"data:image/jpeg;base64,{base64_image}"}}]})

    response = openai.chat.completions.create(model="gpt-4o-mini",messages=messages)
    return response

def parse_data(data):
    data = data.replace("\n", "")
    data.split("%")
    titles = []
    start = False
    current = ""
    for char in data:
        if char == "%":
            if start:
                titles.append(current)
                current = ""
            start = not start
        elif start:
            current += char
    return titles

def grab_json_data():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT library_name, books_json, latitude, longitude FROM libraries")
    result = cursor.fetchall()
    libraries = {row["library_name"]: [json.loads(row["books_json"]), row['latitude'], row['longitude']] for row in result}
    return libraries

mysql = MySQL(app)

if __name__ in "__main__":
    app.run(debug=True)
