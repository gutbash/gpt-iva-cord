from flask import Flask, render_template

app = Flask(__name__)

@app.route('/tos')
def tos():
    return render_template('tos.html')