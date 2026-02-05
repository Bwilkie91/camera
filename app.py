from flask import Flask, render_template, Response, jsonify, request
import cv2
import numpy as np
from ultralytics import YOLO
from deepface import DeepFace
import pytesseract
import mediapipe as mp
import RPi.GPIO as GPIO
import sqlite3
import time
import threading
import pyaudio
import speech_recognition as sr
import librosa
from scapy.all import sniff, Dot11
import io
import PIL.Image

app = Flask(__name__)

# Camera setup
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# AI models
yolo_model = YOLO('yolov8n.pt')
mp_pose = mp.solutions.pose.Pose()

# GPIO setup for motors
GPIO.setmode(GPIO.BCM)
MOTOR_PINS = [23, 24, 25]
for pin in MOTOR_PINS:
    GPIO.setup(pin, GPIO.OUT)
motor_pwm = GPIO.PWM(25, 100)
motor_pwm.start(0)

# SQLite setup
conn = sqlite3.connect('surveillance.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS ai_data (
    date TEXT, time TEXT, individual TEXT, facial_features TEXT, object TEXT,
    pose TEXT, emotion TEXT, scene TEXT, license_plate TEXT, event TEXT, crowd_count INTEGER,
    audio_event TEXT, device_mac TEXT, thermal_signature TEXT
)''')
conn.commit()

# Video recording state
is_recording = False
out = None

# Audio setup
audio = pyaudio.PyAudio()
stream = audio.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
recognizer = sr.Recognizer()

# Wi-Fi setup
devices = set()

# Mock thermal imaging (replace with FLIR Lepton SDK if available)
thermal_frame = np.zeros((80, 60), dtype=np.uint8)

def gen_frames():
    global is_recording, out
    while True:
        success, frame = camera.read()
        if not success:
            break
        if is_recording:
            if out is None:
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                out = cv2.VideoWriter(f'recording_{int(time.time())}.avi', fourcc, 20.0, (1280, 720))
            out.write(frame)
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def gen_thermal_frames():
    global thermal_frame
    while True:
        # Mock thermal data (replace with actual Lepton capture)
        thermal_frame = np.random.randint(0, 255, (80, 60), dtype=np.uint8)
        img = PIL.Image.fromarray(thermal_frame)
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        frame = buffer.getvalue()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def analyze_audio():
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        while True:
            try:
                audio_data = recognizer.listen(source, timeout=1)
                text = recognizer.recognize_google(audio_data)
                return text if text else 'None'
            except:
                return 'None'

def analyze_wifi():
    def packet_handler(pkt):
        if pkt.haslayer(Dot11):
            mac = pkt.addr2
            if mac and mac not in devices:
                devices.add(mac)
                return mac
    sniff(iface='wlan0mon', prn=packet_handler, count=10, timeout=1)
    return devices.pop() if devices else 'None'

def analyze_thermal():
    # Mock thermal signature detection
    return 'Human' if np.mean(thermal_frame) > 100 else 'None'

def analyze_frame():
    global is_recording
    while True:
        if is_recording:
            success, frame = camera.read()
            if success:
                results = yolo_model(frame)
                objects = [results[0].names[int(cls)] for cls in results[0].boxes.cls]
                results_pose = mp_pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                pose = 'Unknown' if not results_pose.pose_landmarks else 'Standing'
                try:
                    emotion = DeepFace.analyze(frame, actions=['emotion'])['dominant_emotion']
                except:
                    emotion = 'Neutral'
                scene = 'Indoor' if np.mean(frame) < 100 else 'Outdoor'
                license_plate = pytesseract.image_to_string(frame) if np.random.random() > 0.8 else 'N/A'
                event = 'None' if np.random.random() > 0.7 else 'Motion Detected'
                crowd_count = len(results[0].boxes) if results[0].boxes else 0
                audio_event = analyze_audio()
                device_mac = analyze_wifi()
                thermal_signature = analyze_thermal()
                data = {
                    'date': time.strftime('%Y-%m-%d'),
                    'time': time.strftime('%H:%M:%S'),
                    'individual': f'Person_{np.random.randint(100)}',
                    'facial_features': f'Feature_{np.random.randint(1000)}',
                    'object': objects[0] if objects else 'None',
                    'pose': pose,
                    'emotion': emotion,
                    'scene': scene,
                    'license_plate': license_plate,
                    'event': event,
                    'crowd_count': crowd_count,
                    'audio_event': audio_event,
                    'device_mac': device_mac,
                    'thermal_signature': thermal_signature
                }
                cursor.execute('''INSERT INTO ai_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                               tuple(data.values()))
                conn.commit()
        time.sleep(10)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/thermal_feed')
def thermal_feed():
    return Response(gen_thermal_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/toggle_recording', methods=['POST'])
def toggle_recording():
    global is_recording, out
    is_recording = not is_recording
    if not is_recording and out:
        out.release()
        out = None
    return jsonify({'recording': is_recording})

@app.route('/toggle_motion', methods=['POST'])
def toggle_motion():
    return jsonify({'motion': request.json['motion']})

@app.route('/move_camera', methods=['POST'])
def move_camera():
    direction = request.json['direction']
    speed = 50
    if direction == 'left':
        GPIO.output(23, True)
        GPIO.output(24, False)
        motor_pwm.ChangeDutyCycle(speed)
    elif direction == 'right':
        GPIO.output(23, False)
        GPIO.output(24, True)
        motor_pwm.ChangeDutyCycle(speed)
    else:
        motor_pwm.ChangeDutyCycle(0)
    return jsonify({'status': 'success'})

@app.route('/get_data')
def get_data():
    cursor.execute('SELECT * FROM ai_data')
    rows = cursor.fetchall()
    return jsonify([dict(zip(['date', 'time', 'individual', 'facial_features', 'object', 'pose', 'emotion', 'scene', 'license_plate', 'event', 'crowd_count', 'audio_event', 'device_mac', 'thermal_signature'], row)) for row in rows])

@app.route('/export_data')
def export_data():
    cursor.execute('SELECT * FROM ai_data')
    rows = cursor.fetchall()
    headers = 'Date,Time,Individual,Facial Features,Object,Pose,Emotion,Scene,License Plate,Event,Crowd Count,Audio Event,Device MAC,Thermal Signature\n'
    csv = headers + '\n'.join([','.join(map(str, row)) for row in rows])
    return Response(csv, mimetype='text/csv', headers={'Content-Disposition': f'attachment;filename=ai_data_{time.strftime("%Y%m%d")}.csv'})

@app.route('/login', methods=['POST'])
def login():
    username = request.json['username']
    password = request.json['password']
    return jsonify({'success': bool(username and password)})

if __name__ == '__main__':
    threading.Thread(target=analyze_frame, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)