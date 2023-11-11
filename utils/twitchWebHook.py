# TODO

import os
import requests
from flask import request
from flask import Flask
import threading

app = Flask(__name__)


@app.route("/")
def entry_point():
    print("hey")
    return "Hello World!"


@app.route("/my_webhook/<user_id>")
def my_webhook(user_id):
    # check_secret(request) # sha256 of your secret and content-length
    data = request.get_json()["data"]
    print(data)
    if len(data) > 0:
        print("on")
    else:
        print("off")
    return "OK"


def get_ip_6():
    import urllib.request

    external_ip = urllib.request.urlopen("https://ident.me").read().decode("utf8")

    print(external_ip)
    return external_ip


# py utils/twitchWebHook.py


def subscribe_to_webhook(user_id):
    print("subscribing")
    ipv6 = get_ip_6()
    endpoint = "https://api.twitch.tv/helix/webhooks/hub"
    topic = "https://api.twitch.tv/helix/streams"
    my_headers = {
        "Client-ID": os.environ["TWITCH_CLIENT_ID"],
        "Authorization": "Bearer " + os.environ["TWITCH_OAUTH_TOKEN"],
    }
    payload = {
        "hub.callback": f"http://[{ipv6}]:5000/my_webhook/{user_id}",
        "hub.mode": "subscribe",
        "hub.topic": f"{topic}?user_id={user_id}",
        "hub.lease_seconds": 864000,
        "hub.secret": os.environ["TWITCH_CLIENT_SECRET"],
    }
    response = requests.post(endpoint, headers=my_headers, data=payload)
    print(response.content)
    print(response)
    return response.ok


if __name__ == "__main__":
    get_ip_6()
    thread1 = threading.Thread(target=app.run, kwargs={"host": "::"})

    thread1.start()

    subscribe_to_webhook("14371185")
    subscribe_to_webhook("161708157")
    subscribe_to_webhook("57781936")
    subscribe_to_webhook("628391901")
    subscribe_to_webhook("184970008")
    subscribe_to_webhook("256864977")
    # app.run(host="::")
