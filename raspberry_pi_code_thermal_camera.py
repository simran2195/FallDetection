import time
import board
import busio
import threading
import numpy as np
import adafruit_mlx90640
from firebase_admin import credentials, initialize_app, storage
from queue import Queue
import bluetooth
import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage
from firebase_admin import db
import cv2

# Added queue to fasten the bluetooth transmission
data_queue = Queue()
fall = False
fall_number = 0


# to accept Bluetooth connection
ESP32_MAC_ADDR = '3C:E9:0E:85:75:06'  
sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
sock.connect((ESP32_MAC_ADDR, 1))  # Use channel 1 for SPP
print("Connected to ESP32**")

# Initialize Firebase SDK
cred = credentials.Certificate("falldetection-386022-firebase-adminsdk-b1tgr-a582aeed27.json")  # Replace with the path to your service account key JSON file
firebase_admin.initialize_app(cred, {
    'storageBucket': 'falldetection-386022.appspot.com',  # Replace with your Firebase Storage bucket name
    'databaseURL': 'https://falldetection-386022-default-rtdb.firebaseio.com'
})


#Connect with MLX90640
i2c = busio.I2C(board.SCL, board.SDA, frequency=400000) # setup I2C
mlx = adafruit_mlx90640.MLX90640(i2c) # begin MLX90640 with I2C comm
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ # set refresh rate
mlx_shape = (24, 32) # mlx90640 shape

frame = np.zeros(mlx_shape[0] * mlx_shape[1]) # 768 pts


# save the image to firebase
def firebase_save_image(frame):
    print("Trying to push image to Firebase...")
    filename = "image.png"
    frame_normalized = (frame - np.min(frame)) / (np.max(frame) - np.min(frame)) * 255
    frame_reshaped = frame_normalized.reshape(mlx_shape).astype(np.uint8)
    resized_image = cv2.resize(frame_reshaped, (640, 480)) # Resize image to 640x480 for Android phone
    flipped_image = cv2.flip(resized_image, 0) # Flip the image upside down
    colored_image = cv2.applyColorMap(flipped_image, cv2.COLORMAP_JET)
    cv2.imwrite(filename, colored_image)

    destination_path = 'images/image.png'
    bucket = storage.bucket()
    blob = bucket.blob(destination_path)
    blob.upload_from_filename(filename)

    # Opt: if you want to make public access from the URL
    blob.make_public()

    print("Your file URL:", blob.public_url)

    # Get a reference to the Firebase Realtime Database
    ref = db.reference('/fall_detection')

    # Write new data to the database
    new_data = 77

    ref.push(new_data)  # Push the new data under the 'users' node

    print('Data written successfully!')


# receive bluetooth data
def bluetooth_data_processing():
    while True:
        data = sock.recv(1024).decode('utf-8')
        values = data.split('\r\n')

        for value_str in values:
            print("Received data:", value_str)
            firebase_save_image(frame)
            # Process the received data as needed

        time.sleep(0.1)  # Adjust the sleep duration as needed


# capture the frame of camera when fall notification is received via Bluetooth
def capture_data():
    while True:
        mlx.getFrame(frame) # read mlx90640
        time.sleep(0.25)  # Adjust the sleep duration as needed

bluetooth_thread = threading.Thread(target=bluetooth_data_processing)
bluetooth_thread.start()

data_capture_thread = threading.Thread(target=capture_data)
data_capture_thread.start()

while True:
    # Check if there is data in the queue
    if not data_queue.empty():
        data = data_queue.get()
        print("Bluetooth Data Received:", data)
