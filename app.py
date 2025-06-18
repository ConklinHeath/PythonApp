from flask import Flask, render_template
import File
import json

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/Library")
def library():
    allLibraries = File.read_file('library.txt')
    libraryObj = json.loads(allLibraries)
    return render_template("library.html", libraries=libraryObj)

@app.route("/Books")
def book():
    return render_template("book.html")

@app.route("/Photo")
def photo():
    return render_template("photo.html")

if __name__ in "__main__":
    app.run(debug=True)

#updated line