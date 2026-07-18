from flask import Flask, send_from_directory

app = Flask(__name__)

@app.route("/wiitv")
def wiitv():
    return send_from_directory("assets", "maintenance.swf", mimetype='application/x-shockwave-flash')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)
