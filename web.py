from flask import Flask, render_template

app = Flask(__name__)

@app.route('/policies')
def policies():
    return render_template('policies.html')

if __name__ == '__main__':
    app.run()