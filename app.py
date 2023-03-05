from flask import Flask, render_template,request
import json


app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ProcessUserinfo/',methods=['POST'])
def ProcessUserinfo():
    userinfo=request.args.get("food")
    print()
    print(userinfo)
    print()
    return('/')

if __name__ == "__main__":
    app.run(debug=True)
    