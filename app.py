import openai
import requests
from flask import *
import File
import json
from PIL import Image
import io
from openai import  OpenAI
import base64
import json

app = Flask(__name__)

openai.api_key = API_KEY

bot_personality = "You are a helpful assistant."
bot_prompt = "Find all the book titles in this image. For each book title, use the following format. Brackets represent what you replace, dont print out the brackets: %[Book Title]%. If no book title is found use the following format: %NONE%. Dont number the books."

@app.route("/")
def index():
    print("libraryObj")
    return render_template("index.html")

@app.route("/Library")
def library():
    allLibraries = File.read_file('library.json')
    libraryObj = json.loads(allLibraries)
    print(libraryObj)
    return render_template("library.html", libraries=libraryObj)

@app.route("/Books")
def book():
    allLibraries = File.read_file('library.json')
    libraryObj = json.loads(allLibraries)
    print(libraryObj)
    return render_template("book.html", libraries=libraryObj)

@app.route("/Photo", methods=['POST', 'GET'])
def photo():
    if request.method == 'POST':
        libraryForm = request.form.get("Library")
        file = request.files.get('PhotoDrop')
        print(file)
        image = Image.open(file.stream)
        print(f"Image format: {image.format}, size: {image.size}, mode: {image.mode}")
        image_path = "temp_uploaded_image.png"
        image.save(image_path)
        response = chatbot(image_path)
        books = response.choices[0].message.content
        books = parse_data(books)
        data = {libraryForm : books}
        with open("library.json", "r") as json_file:
            file_data = json.loads(json_file.read())
        file_data.update(data)
        with open("library.json", "w") as json_file:
            json_file.write(json.dumps(file_data))
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

if __name__ in "__main__":
    app.run(debug=True)
