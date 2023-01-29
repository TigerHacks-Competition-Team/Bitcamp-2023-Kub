from flask import Flask
import yt_dlp
from google.cloud import storage
import os
from flask import Response, request
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
@app.route("/")
def hello_world():
    return "<p>This is a Hello World application</p>"

final_filename = None

def yt_dlp_monitor(d):
    global final_filename
    if final_filename is None:
        final_filename = d.get('info_dict').get('_filename')

@app.route("/yt2mp3", methods = ['POST'])
def yt2mp3():
    global final_filename
    extension = 'wav'

    ydl_opts = {
        'format': f'{extension}/bestaudio/best',
        # Extract audio using ffmpeg
        'postprocessors': [{  
            'key': 'FFmpegExtractAudio',
            'preferredcodec': f'{extension}',
        }],
        "outtmpl": "/tmp/%(id)s.%(ext)s",
        "no-part": True,
        "progress_hooks": [yt_dlp_monitor]
    }

    URL = [request.json["url"]]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            error_code = ydl.download(URL)
        except:
            return('', 500)

        bucket = "hoya-hacks-video-files"

        storage_client = storage.Client()

        bucket = storage_client.get_bucket(bucket, timeout = 60)

        id = final_filename.split("/")[2].split(".")[0]

        mp3_path = "/tmp/" + id + f".{extension}"

        file = bucket.blob(id + f".{extension}")

        print("Uploading Audio to Bucket")
        file.upload_from_filename(mp3_path)

        #file.make_public()

        #os.remove(mp3_path)

        final_filename = None

        if request.method == 'POST':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '3600'
            }

            return("gs://hoya-hacks-video-files/" + id + f".{extension}", 200, headers)

    headers = {
        'Content-Type':'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
    }

    return ('', 200, headers)

class AppURLOpener(urllib.request.FancyURLopener):
    version = "Mozilla/5.0"

@app.route("/video2mp3", methods = ['POST'])
def video2mp3(request):
    extension = 'wav'
    url = request.json["video"]
    print(url.split("/")[9])

    filename= url.split("/")[-1]
    opener = AppURLOpener()
    response = opener.open(url)
    outfile = open(f"/tmp/{filename}", "wb")
    outfile.write(response.read())
    
    videoPath = f"/tmp/{filename}"
    audioPath = f"/tmp/{filename}.{extension}"
    cmd = f"ffmpeg -i {videoPath} -vn {audioPath}"
    os.system(cmd)

    bucket = "hoya-hacks-video-files"
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket, timeout = 60)

    file = bucket.blob(f"{filename}.{extension}")
    file.upload_from_filename(audioPath)

    outfile.close()

    if request.method == 'POST':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '3600'
            }

            return("gs://hoya-hacks-video-files/" + f"{filename}.{extension}", 200, headers)

    headers = {
        'Content-Type':'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
    }

    return ('', 200, headers)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000)
