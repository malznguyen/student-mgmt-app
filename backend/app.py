from flask import Flask, jsonify, send_from_directory
import os
app = Flask(__name__, static_folder="../frontend", static_url_path="/")
@app.get("/api/health")
def health(): return jsonify({"ok": True})
@app.route("/")
def root(): return send_from_directory(app.static_folder, "index.html")
@app.route("/pages/<path:p>")
def pages(p): return send_from_directory(os.path.join(app.static_folder, "pages"), p)
if __name__ == "__main__": app.run(debug=True)
