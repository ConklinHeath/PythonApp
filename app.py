import math
import openai
import requests
from flask import *
from geopy.distance import geodesic
import pygame
import sys
import File
from PIL import Image
import io
from openai import OpenAI
import base64
import json
from flask_mysqldb import MySQL
import MySQLdb.cursors
from geopy import *
import pygame
import math
import random
import time



app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'mydatabase'

GOOGLE_VISION_API_KEY = ""

API_KEY = ""
openai.api_key = API_KEY

bot_personality = "You are a helpful assistant."
bot_prompt = "Find all the book titles in this image. For each book title, use the following format. Brackets represent what you replace, dont print out the brackets: %[Book Title]%. If no book title is found use the following format: %NONE%. Dont number the books."

@app.route("/")
def index():
    print("libraryObj")
    return render_template("index.html")

@app.route("/Library", methods=['POST', 'GET'])
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

        vision_data, ocr_text = google_vision(image_path)

        print("OCR Text:", ocr_text)

        text_got = display_image_data(vision_data['responses'][0], image_path) # Pass the first response which has textAnnotations

        books = parse_data(text_got)

        books_json = json.dumps(books)

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT library_name, books_json, latitude, longitude FROM libraries")
        result = cursor.fetchall()

        dist_new_library = 0.0000
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

def google_vision(image_path):
    with open(image_path, 'rb') as img:
        img_content = base64.b64encode(img.read()).decode('utf-8')
    vision_url = f'https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}'

    payload = {
        "requests": [
            {
                "image": {
                    "content": img_content
                },
                "features": [
                    {
                        "type": "TEXT_DETECTION"
                    }
                ]
            }
        ]
    }

    response = requests.post(vision_url, json=payload)
    vision_data = response.json()
    print("Raw Vision API Response:", vision_data)

    # Extract text safely
    text = vision_data.get('responses', [{}])[0].get('fullTextAnnotation', {}).get('text', '')
    if not text:
        text = "No text found."

    # Return both full response and extracted text
    return vision_data, text

def parse_data(groups):
    print("0--------")
    print(groups)
    entries = []
    for group in groups:
        if len(group) <= 2:
            continue
        title = " ".join(word.strip() for word in group if word.strip())
        if title.upper() == "NONE" or title.strip() == "":
            entries.append({"title": "NONE"})
        else:
            title = title.title()
            entries.append({"title": title})
    print("00--------")
    print(entries)
    return entries

def grab_json_data():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT library_name, books_json, latitude, longitude FROM libraries")
    result = cursor.fetchall()
    libraries = {row["library_name"]: [json.loads(row["books_json"]), row['latitude'], row['longitude']] for row in result}
    return libraries

def display_image_data(response, image_path, max_iterations=3, rays_per_box=5, display_seconds=5):
    max_length = 100
    pil_image = Image.open(image_path).convert("RGB")
    image_width, image_height = pil_image.size
    mode = pil_image.mode
    data = pil_image.tobytes()

    pygame.init()
    screen = pygame.display.set_mode((image_width, image_height))
    pygame.display.set_caption('Vision API Grouped Bounding Boxes')

    image_surface = pygame.image.fromstring(data, pil_image.size, mode)

    annotations = response.get("textAnnotations", [])[1:]  # skip first, full text

    def get_edges(vertices):
        return [(vertices[i], vertices[(i + 1) % 4]) for i in range(4)]

    def midpoint(p1, p2):
        return ((p1['x'] + p2['x']) / 2, (p1['y'] + p2['y']) / 2)

    def dist(p1, p2):
        return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

    # Only opposite edge pairs: (0,2) and (1,3)
    def furthest_opposite_edges_midpoints(vertices):
        edges = get_edges(vertices)
        midpoints = [midpoint(e[0], e[1]) for e in edges]

        pairs = [(0, 2), (1, 3)]

        max_d = -1
        chosen_pair = (0, 2)
        for i, j in pairs:
            d = dist(midpoints[i], midpoints[j])
            if d > max_d:
                max_d = d
                chosen_pair = (i, j)

        return midpoints[chosen_pair[0]], midpoints[chosen_pair[1]]

    def closest_opposite_edges_midpoints(vertices):
        edges = get_edges(vertices)
        midpoints = [midpoint(e[0], e[1]) for e in edges]

        pairs = [(0, 2), (1, 3)]

        min_d = math.inf
        chosen_pair = (0, 2)
        for i, j in pairs:
            d = dist(midpoints[i], midpoints[j])
            if d < min_d:
                min_d = d
                chosen_pair = (i, j)

        return midpoints[chosen_pair[0]], midpoints[chosen_pair[1]]

    def ray_direction(p1, p2):
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length == 0:
            return (1, 0)
        return (dx / length, dy / length)


    def ray_intersects_box(origin, direction, vertices):
        ox, oy = origin
        dx, dy = direction
        ray_end = (ox + dx * max_length, oy + dy * max_length)

        def segments_intersect(p1, p2, q1, q2):
            def cross(v1, v2):
                return v1[0] * v2[1] - v1[1] * v2[0]

            r = (p2[0] - p1[0], p2[1] - p1[1])
            s = (q2[0] - q1[0], q2[1] - q1[1])
            denom = cross(r, s)

            if denom == 0:
                return False  # Parallel or colinear

            qp = (q1[0] - p1[0], q1[1] - p1[1])
            t = cross(qp, s) / denom
            u = cross(qp, r) / denom

            return 0 <= t <= 1 and 0 <= u <= 1

        ray_seg = (origin, ray_end)

        for i in range(4):
            v1 = vertices[i]
            v2 = vertices[(i + 1) % 4]
            box_seg = ((v1["x"], v1["y"]), (v2["x"], v2["y"]))
            if segments_intersect(ray_seg[0], ray_seg[1], box_seg[0], box_seg[1]):
                return True

        return False

    # Prepare boxes data
    boxes = []
    for ann in annotations:
        vertices = ann["boundingPoly"]["vertices"]
        # fill missing coords with 0
        for v in vertices:
            if "x" not in v:
                v["x"] = 0
            if "y" not in v:
                v["y"] = 0
        furthest_mid1, furthest_mid2 = furthest_opposite_edges_midpoints(vertices)
        initial_dir = ray_direction(furthest_mid1, furthest_mid2)
        boxes.append({
            "vertices": vertices,
            "ray_dir": initial_dir,
            "rays": [],
            "text": ann.get("description", ""),  # Extract the detected text here
            "group": None,
        })

    def cast_rays(box, rays_per_box=5, angle_spread_degrees=10):
        cx = sum(v["x"] for v in box["vertices"]) / 4
        cy = sum(v["y"] for v in box["vertices"]) / 4
        base_point = (cx, cy)

        dx, dy = box['ray_dir']
        base_angle = math.atan2(dy, dx)
        angle_spread = math.radians(angle_spread_degrees)

        rays = []
        for i in range(rays_per_box):
            if rays_per_box == 1:
                offset_angle = 0
            else:
                offset_angle = angle_spread * (i / (rays_per_box - 1) - 0.5)
            angle = base_angle + offset_angle
            rays.append((base_point, (math.cos(angle), math.sin(angle))))

        box['rays'] = rays

    class UnionFind:
        def __init__(self, n):
            self.parent = list(range(n))

        def find(self, a):
            while self.parent[a] != a:
                self.parent[a] = self.parent[self.parent[a]]
                a = self.parent[a]
            return a

        def union(self, a, b):
            pa = self.find(a)
            pb = self.find(b)
            if pa != pb:
                self.parent[pb] = pa

    def group_boxes(boxes):
        uf = UnionFind(len(boxes))
        for box in boxes:
            cast_rays(box)

        for i, box_i in enumerate(boxes):
            for origin, direction in box_i['rays']:
                for j, box_j in enumerate(boxes):
                    if i == j:
                        continue
                    if ray_intersects_box(origin, direction, box_j["vertices"]):
                        uf.union(i, j)

        groups = {}
        for i in range(len(boxes)):
            p = uf.find(i)
            groups.setdefault(p, []).append(boxes[i])

        return list(groups.values())

    def average_ray_direction(group):
        sum_x = 0
        sum_y = 0
        for b in group:
            dx, dy = b["ray_dir"]
            sum_x += dx
            sum_y += dy
        length = math.hypot(sum_x, sum_y)
        if length == 0:
            return (1, 0)
        return (sum_x / length, sum_y / length)

    def refine_ray_directions(groups):
        max_angle_diff = math.radians(30)
        for group in groups:
            avg_dir = average_ray_direction(group)
            for box in group:
                dx, dy = box["ray_dir"]
                dot = dx * avg_dir[0] + dy * avg_dir[1]
                dot = max(min(dot, 1), -1)
                angle = math.acos(dot)
                if angle > max_angle_diff:
                    p1, p2 = closest_opposite_edges_midpoints(box["vertices"])
                    box["ray_dir"] = ray_direction(p1, p2)

    def final_group_merge(boxes):
        uf = UnionFind(len(boxes))

        for box in boxes:
            cast_rays(box)

        for i, box_i in enumerate(boxes):
            for origin, direction in box_i['rays']:
                for j, box_j in enumerate(boxes):
                    if i == j:
                        continue
                    if ray_intersects_box(origin, direction, box_j["vertices"]):
                        uf.union(i, j)

        groups_map = {}
        for i in range(len(boxes)):
            p = uf.find(i)
            groups_map.setdefault(p, []).append(boxes[i])

        return list(groups_map.values())

    # Main iterative grouping + refining
    groups = []
    for iteration in range(max_iterations):
        groups = group_boxes(boxes)
        refine_ray_directions(groups)

    # Final merge to catch any leftover group splits
    groups = final_group_merge(boxes)

    # Assign colors to groups
    group_colors = {}
    for i in range(len(groups)):
        group_colors[i] = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))

    running = True
    clock = pygame.time.Clock()

    start_time = time.time()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Automatically quit after display_seconds
        if time.time() - start_time > display_seconds:
            running = False

        screen.fill((0, 0, 0))
        screen.blit(image_surface, (0, 0))

        # Draw boxes colored by group
        for box in boxes:
            # Assign group index for color
            group_idx = None
            for gi, group in enumerate(groups):
                if box in group:
                    group_idx = gi
                    break
            color = group_colors.get(group_idx, (255, 0, 0))
            points = [(v["x"], v["y"]) for v in box["vertices"]]
            pygame.draw.polygon(screen, color, points, 3)

        # Draw rays (white)
        for box in boxes:
            for origin, direction in box['rays']:
                ox, oy = origin
                dx, dy = direction
                end_pos = (ox + dx * max_length, oy + dy * max_length)
                pygame.draw.line(screen, (255, 255, 255), (ox, oy), end_pos, 1)
                pygame.draw.circle(screen, (255, 255, 255), (int(ox), int(oy)), 3)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

    # Prepare output: groups as lists of boxes with titles or bounding info you want
    # For example, each box returns its vertices and maybe text?
    pygame.quit()

    # Return only grouped texts
    result_groups = []
    for group in groups:
        group_texts = [box["text"] for box in group if box["text"].strip() != ""]
        if group_texts:
            result_groups.append(group_texts)

    return result_groups


mysql = MySQL(app)

if __name__ == "__main__":
    app.run(debug=True)
