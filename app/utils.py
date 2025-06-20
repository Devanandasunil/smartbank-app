from functools import wraps
from flask import make_response, Response
from .models import Account, db
import random

def nocache(view) -> callable:
    @wraps(view)
    def no_cache(*args, **kwargs) -> Response:
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return no_cache

def get_or_create_account(user):
    if not user.account:
        account_number = "SB" + str(random.randint(10000000, 99999999))
        account = Account(user_id=user.id, account_number=account_number, balance=0.0)
        db.session.add(account)
        db.session.commit()
    return user.account

# 👇 NEW: extract_face_encoding function
import face_recognition
import numpy as np
import base64
import cv2

def extract_face_encoding(base64_image_data):
    if "base64," in base64_image_data:
        base64_image_data = base64_image_data.split("base64,")[1]

    img_data = base64.b64decode(base64_image_data)
    np_array = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

    face_locations = face_recognition.face_locations(img)
    if len(face_locations) != 1:
        return None

    face_encoding = face_recognition.face_encodings(img, face_locations)[0]
    return face_encoding

from googletrans import Translator

translator = Translator()

def auto_translate(text, target_lang='ml'):  # 'ml' for Malayalam
    try:
        result = translator.translate(text, dest=target_lang)
        return result.text
    except Exception as e:
        return text  # fallback to original

import face_recognition
import numpy as np
import base64
import cv2
from PIL import Image
from io import BytesIO

def get_face_encoding_from_base64(data_url):
    try:
        # Clean the base64
        header, encoded = data_url.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        img_array = np.frombuffer(img_bytes, np.uint8)

        # Decode image using OpenCV
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Get face encodings
        encodings = face_recognition.face_encodings(rgb_image)
        return encodings

    except Exception as e:
        print("Face encoding error:", e)
        return []


