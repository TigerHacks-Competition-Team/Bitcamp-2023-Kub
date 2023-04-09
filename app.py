from flask import Flask
import yt_dlp
import os
import shutil
from flask import Response, request
import urllib.request
import subprocess
import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage
from firebase_admin import firestore
from basic_pitch.inference import predict_and_save

cred = credentials.Certificate("./bitcamp-2023-firebase-adminsdk-zfq9y-9abf423e33.json")
fb = firebase_admin.initialize_app(cred)
bucket = storage.bucket("bitcamp-2023.appspot.com")
db = firestore.client()
app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>This is a Hello World application</p>"


final_filename = None


def yt_dlp_monitor(d):
    global final_filename
    if final_filename is None:
        final_filename = d.get('info_dict').get('_filename')


@app.route("/yt2wav", methods=['POST', 'OPTIONS'])
def yt2wav():
    # intercept options request
    if request.method == "OPTIONS":
        headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST",
        "Access-Control-Expose-Headers": "Content-Length, X-JSON",
        "Access-Control-Allow-Headers":
        "X-Client-Info, Content-Type, Authorization, Accept, Accept-Language, X-Authorization",
        }
        return ("OK", 200, headers)

    # init ydl options (wav format)
    global final_filename
    extension = 'mp3'

    ydl_opts = {
        'format': f'{extension}/worstaudio/worst',
        # Extract audio using ffmpeg
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': f'{extension}',
        }],
        "no-part": True,
        "progress_hooks": [yt_dlp_monitor]
    }



    # parse request params
    docID = request.json["docID"]  # document ID in firestore
    doc = db.collection("songs").document(docID).get().to_dict()
    url = [doc["url"]]  # youtube url

    print(f"Getting wav file for: {url} with docID: {docID}")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            error_code = ydl.download(url)
        except:
            return ('', 500)

        files = os.listdir("./")
        print(files)
        files = [file for file in files if os.path.isfile(file) and len(file.split(".")) > 1 and file.split(".")[1] == "mp3"]

        wav_path = files[0]

        storage_path = f"songs/{docID}/original.mp3"
        file = bucket.blob(storage_path)

        print("Uploading Audio to Bucket")
        file.upload_from_filename(wav_path)

        final_filename = None

        # update firestore document with wav link
        db.collection(u"songs").document(docID).update({u"original": storage_path})

        if request.method == 'POST':
            headers = {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST",
                "Access-Control-Expose-Headers": "Content-Length, X-JSON",
                "Access-Control-Allow-Headers":
                "X-Client-Info, Content-Type, Authorization, Accept, Accept-Language, X-Authorization",
            }

            return ("SUCCESS", 200, headers)

    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST",
        "Access-Control-Expose-Headers": "Content-Length, X-JSON",
        "Access-Control-Allow-Headers":"X-Client-Info, Content-Type, Authorization, Accept, Accept-Language, X-Authorization",
    }

    return ('', 200, headers)


@app.route("/wav2piano", methods=['POST', 'OPTIONS'])
def wav2piano():
    # intercept options request
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Expose-Headers": "Content-Length, X-JSON",
            "Access-Control-Allow-Headers":
                "X-Client-Info, Content-Type, Authorization, Accept, Accept-Language, X-Authorization",
        }
        return ("OK", 200, headers)

    # parse request params
    docID = request.json["docID"]  # document ID in firestore
    doc = db.collection("songs").document(docID).get().to_dict()
    path = doc["original"]  # cloud storage path

    # download original wav asset
    print("download original asset")
    blob = bucket.blob(path)
    blob.download_to_filename("./original.mp3")

    # run spleeter
    print("running spleeter")
    try:
        os.mkdir("output")
    except:
        print("output directory already exists")

    subprocess.Popen(["sudo", "chmod", "777", "output/"]).wait(timeout=None)
    cmd = ["python3", "-m", "spleeter", "separate", "--verbose", "-p", "spleeter:5stems", "--mwf", "-o", "output/", "./original.mp3"]
    subprocess.Popen(cmd).wait(timeout=None)

    print("spleeter finished")
    subprocess.Popen(["ffmpeg", "-i", "output/original/vocals.wav", "-b:a", "96k", "-acodec", "mp3", "output/original/vocals.mp3"]).wait(timeout=None)
    subprocess.Popen(["ffmpeg", "-i", "output/original/piano.wav", "-b:a", "96k", "-acodec", "mp3", "output/original/piano.mp3"]).wait(timeout=None)
    subprocess.Popen(["ffmpeg", "-i", "output/original/drums.wav", "-b:a", "96k", "-acodec", "mp3", "output/original/bass.mp3"]).wait(timeout=None)
    subprocess.Popen(["ffmpeg", "-i", "output/original/bass.wav", "-b:a", "96k", "-acodec", "mp3", "output/original/drums.mp3"]).wait(timeout=None)
    subprocess.Popen(["ffmpeg", "-i", "output/original/other.wav", "-b:a", "96k", "-acodec", "mp3", "output/original/other.mp3"]).wait(timeout=None)

    vocals_path = "output/original/vocals.mp3"
    piano_path = "output/original/piano.mp3"
    drums_path = "output/original/drums.mp3"
    bass_path = "output/original/bass.mp3"
    other_path = "output/original/other.mp3"

    vocals_storage = f"songs/{docID}/vocals.mp3"
    piano_storage = f"songs/{docID}/piano.mp3"
    drums_storage = f"songs/{docID}/drums.mp3"
    bass_storage = f"songs/{docID}/bass.mp3"
    other_storage = f"songs/{docID}/other.mp3"

    vocals_file = bucket.blob(vocals_storage)
    piano_file = bucket.blob(piano_storage)
    drums_file = bucket.blob(drums_storage)
    bass_file = bucket.blob(bass_storage)
    other_file = bucket.blob(other_storage)

    vocals_file.upload_from_filename(vocals_path)
    piano_file.upload_from_filename(piano_path)
    drums_file.upload_from_filename(drums_path)
    bass_file.upload_from_filename(bass_path)
    other_file.upload_from_filename(other_path)

    updated_doc = {
        u"vocals": vocals_storage,
        u"piano": piano_storage,
        u"drums": drums_storage,
        u"bass": bass_storage,
        u"other": other_storage,

    }

    # update firestore document with wav link
    print("uploading to firebase")
    db.collection(u"songs").document(docID).update(updated_doc)

    if request.method == 'POST':
        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Expose-Headers": "Content-Length, X-JSON",
            "Access-Control-Allow-Headers":
                "X-Client-Info, Content-Type, Authorization, Accept, Accept-Language, X-Authorization",
        }

        return ("SUCCESS", 200, headers)


@app.route("/piano2midi", methods=['POST', 'OPTIONS'])
def piano2midi():
    # intercept options request
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Expose-Headers": "Content-Length, X-JSON",
            "Access-Control-Allow-Headers":
                "X-Client-Info, Content-Type, Authorization, Accept, Accept-Language, X-Authorization",
        }
        return ("OK", 200, headers)

    # parse request params
    docID = request.json["docID"]  # document ID in firestore
    doc = db.collection("songs").document(docID).get().to_dict()
    path = doc["piano"]  # cloud storage path

    # download piano wav asset
    print("downloading piano wav asset")
    blob = bucket.blob(path)
    blob.download_to_filename("./piano.mp3")

    try:
        shutil.rmtree("./output", ignore_errors=False, onerror=None)
    except:
        print("No dir output")

    try:
        os.mkdir("./output")
    except:
        print("Couldnt create output dir")

    # run base pitch to convert to midi
    print("running base pitch")
    predict_and_save(
        ["./piano.mp3"],
        "./output",
        True,
        False,
        False,
        True,
    )

    midi_path = "output/piano_basic_pitch.mid"
    csv_path = "output/piano_basic_pitch.csv"

    midi_storage = f"songs/{docID}/midi.mid"
    csv_storage = f"songs/{docID}/midi.csv"

    midi_file = bucket.blob(midi_storage)
    csv_file = bucket.blob(csv_storage)

    midi_file.upload_from_filename(midi_path)
    csv_file.upload_from_filename(csv_path)

    print("upload to firebase")
    updated_doc = {
        u"midi": midi_storage,
        u"csv": csv_storage,

    }

    # update firestore document with wav link
    db.collection(u"songs").document(docID).update(updated_doc)

    if request.method == 'POST':
        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Expose-Headers": "Content-Length, X-JSON",
            "Access-Control-Allow-Headers":
                "X-Client-Info, Content-Type, Authorization, Accept, Accept-Language, X-Authorization",
        }

        return ("SUCCESS", 200, headers)
class AppURLOpener(urllib.request.FancyURLopener):
    version = "Mozilla/5.0"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
