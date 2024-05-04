from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase
import psycopg2
import psycopg2.extras
import re
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "hjhjsdahhds"
socketio = SocketIO(app)
app.secret_key = 'cairocoders-ednalan'

rooms = {}


DB_HOST = "localhost"
DB_NAME = "food4paws"
DB_USER = "postgres"
DB_PASS = "sanika@11"

conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

def connect_to_database():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST
    )
    return conn

@app.route('/')
def landing_page():
    return render_template('landingpage.html')

@app.route('/register_button')
def register_button():
    return redirect(url_for('show_register_form'))

@app.route('/show_register_form', methods=['GET', 'POST'])
def show_register_form():
    if request.method == 'POST':
        process_register()
        return redirect(url_for('login'))
    return render_template('register.html')

def process_register():
    username = request.form['username']
    password = generate_password_hash(request.form['password'])
    user_type = request.form['user_type']
    email = request.form['email']
    phone = request.form['phone']
    location = request.form['location']

    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO Users (Username, Password, UserType, Email, Phone, Location)
                      VALUES (%s, %s, %s, %s, %s, %s)''',
                   (username, password, user_type, email, phone, location))
    conn.commit()
    conn.close()

@app.route('/login_button')
def login_button():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        latitude = request.form.get('latitude')  # Use get() to handle cases where latitude might not be present
        longitude = request.form.get('longitude')  

        conn = connect_to_database()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT * FROM Users WHERE Username = %s', (username,))
        user_data = cursor.fetchone()

        if user_data and check_password_hash(user_data['password'], password):
            session['loggedin'] = True
            session['username'] = username
            session['usertype'] = user_data['usertype']

            if latitude and longitude:
                cursor.execute('UPDATE Users SET Latitude = %s, Longitude = %s WHERE Username = %s', (latitude, longitude, username))
                conn.commit()

            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/home')
def home():
    if 'loggedin' in session:
        if session['usertype'] == 'donor':
            conn = connect_to_database()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Feeders')
            feeders_data = cursor.fetchall()
            conn.close()
            return render_template('home.html', feeders_data=feeders_data)
        elif session['usertype'] == 'feeder':
            # Add logic to fetch and display donor-related information
            conn = connect_to_database()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Donors')
            donors_data = cursor.fetchall()
            conn.close()
            return render_template('home.html', donors_data=donors_data)  # Assuming you have donor data to display
    else:
        return redirect(url_for('login'))
@app.route('/messages')
def messages():
    if 'loggedin' in session:
        username = session['username']
        conn = connect_to_database()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Messages WHERE SenderID = (SELECT UserID FROM Users WHERE Username = %s)', (username,))
        messages_data = cursor.fetchall()
        conn.close()
        return render_template('messages.html', messages_data=messages_data)
    else:
        return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'loggedin' in session:
        username = session['username']
        conn = connect_to_database()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Users WHERE Username = %s', (username,))
        user_data = cursor.fetchone()
        conn.close()
        return render_template('profile.html', user_data=user_data)
    else:
        return redirect(url_for('login'))

@app.route('/submit_donation', methods=['POST'])
def submit_donation():
    if 'loggedin' in session:
        if request.method == 'POST':
            food_type = request.form['food_type']
            quantity = request.form['quantity']
            animal_type = request.form['animal_type']
            rating = request.form['rating']
            address = request.form['address']
            latitude = request.form['latitude']
            longitude = request.form['longitude']
            donor_username = session['username']  # Get the username of the logged-in user

            # Connect to the database
            conn = connect_to_database()
            cursor = conn.cursor()

            # Fetch the id of the logged-in user from the Users table
            cursor.execute('SELECT userid FROM Users WHERE username = %s', (donor_username,))
            donor_id = cursor.fetchone()[0]  # Get the first column (id) of the first row

            # Insert the donation record into the Donors table
            cursor.execute('''INSERT INTO Donors (DonorID, FoodType, Quantity, AnimalType, Rating, Address, Latitude, Longitude) 
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                              (donor_id, food_type, quantity, animal_type, rating, address, latitude, longitude))
            conn.commit()

            # Fetch the inserted donation information
            cursor.execute('''SELECT * FROM Donors WHERE DonorID = %s AND FoodType = %s AND Quantity = %s AND AnimalType = %s AND Rating = %s AND Address = %s AND Latitude = %s AND Longitude = %s''',
                              (donor_id, food_type, quantity, animal_type, rating, address, latitude, longitude))
            donation_data = cursor.fetchone()
            conn.close()

            # Display a success message
            success_message = "Your donation request has been successfully posted."

            # Render the profile page with the success message
            return render_template('profile.html', user_data=None, success_message=success_message, donation_data=donation_data)
    else:
        return redirect(url_for('login'))


@app.route('/show_donor_location')
def show_donor_location():
    username = session.get('username')
    
    # Fetch latitude and longitude of the logged-in user from the database
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute('SELECT Latitude, Longitude FROM Users WHERE Username = %s', (username,))
    user_location_data = cursor.fetchone()
    conn.close()

    if user_location_data:
        user_latitude, user_longitude = user_location_data
    else:
        # Default values if user's location is not found
        user_latitude, user_longitude = None, None
    
    donor_latitude = request.args.get('latitude')
    donor_longitude = request.args.get('longitude')

    return render_template('donorsmap.html', user_latitude=user_latitude, user_longitude=user_longitude, donor_latitude=donor_latitude, donor_longitude=donor_longitude)

    
@app.route('/show_feeder_location')
def show_feeder_location():
    username = session.get('username')
    
    # Fetch latitude and longitude of the logged-in user from the database
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute('SELECT Latitude, Longitude FROM Users WHERE Username = %s', (username,))
    user_location_data = cursor.fetchone()
    conn.close()

    if user_location_data:
        user_latitude, user_longitude = user_location_data
    else:
        # Default values if user's location is not found
        user_latitude, user_longitude = None, None
    
    feeder_latitude = request.args.get('latitude')
    feeder_longitude = request.args.get('longitude')

    return render_template('feedersmap.html', user_latitude=user_latitude, user_longitude=user_longitude, feeder_latitude=feeder_latitude, feeder_longitude=feeder_longitude)



@app.route('/map')
def show_all_feeders_map():
    # Assuming you have a way to determine the user's role (e.g., from session data)
    user_role = session.get('usertype')  # Get the user's role from session
    print("User role from session:", user_role) 
    
    conn = connect_to_database()
    cursor = conn.cursor()

    if user_role == 'donor':
        # Show all feeders
        cursor.execute('SELECT Latitude, Longitude, username FROM Feeders')
        feeders_data = cursor.fetchall()
    elif user_role == 'feeder':
        # Show all donors
        cursor.execute('SELECT Latitude, Longitude, username FROM Donors')
        feeders_data = cursor.fetchall()
    else:
        # Default behavior (don't fetch anything)
        feeders_data = []
        
    conn.close()
    
    feeders = [{'latitude': float(row[0]), 'longitude': float(row[1]), 'name': row[2]} for row in feeders_data]

    return render_template('allfeeders_map.html', feeders=feeders)

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Clear the session
    return redirect(url_for('landing_page'))





def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)

        if code not in rooms:
            break

    return code

@app.route("/chat", methods=["POST", "GET"])
def homechat():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("homechat.html", error="Please enter a name.", code=code, name=name)

        if join != False and not code:
            return render_template("homechat.html", error="Please enter a room code.", code=code, name=name)

        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template("homechat.html", error="Room does not exist.", code=code, name=name)

        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("homechat.html")

@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("homechat"))

    return render_template("room.html", code=room, messages=rooms[room]["messages"])

@socketio.on("message")
def handle_message(data):
    room = session.get("room")
    if room not in rooms:
        return 

    content = {
        "name": session.get("name"),
        "message": data["data"]
    }
    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} said: {data['data']}")


    socketio.emit("notification", {"message": "You have a new message!"}, room=room)


@socketio.on("connect")
def handle_connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)
    rooms[room]["members"] += 1
    print(f"{name} joined room {room}")

    

@socketio.on("disconnect")
def handle_disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]

    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left the room {room}")





if __name__ == '__main__':
    app.run(debug=True)
    socketio.run(app, debug=True)