# upload.py
from flask import request, jsonify, send_file
import os, uuid

UPLOAD_DIR = "/tmp"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def register(app):
    @app.route("/upload", methods=["POST"])
    def upload_file():
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']
        ext = os.path.splitext(file.filename)[-1]
        filename = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        file.save(save_path)

        # Return a public download link
        download_url = f"https://{request.host}/file-download/{filename}"
        return jsonify({"download_url": download_url})

    @app.route("/file-download/<filename>", methods=["GET"])
    def download_file(filename):
        filepath = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        return send_file(filepath, as_attachment=False)
