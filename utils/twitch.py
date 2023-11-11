# TODO
import os
import requests


class Twitch:
    def __init__(self):
        self.headers = {}
        self.login()

    def login(self):
        body = {
            "client_id": os.environ["TWITCH_CLIENT_ID"],
            "client_secret": os.environ["TWITCH_CLIENT_SECRET"],
            "grant_type": "client_credentials",
        }
        r = requests.post("https://id.twitch.tv/oauth2/token", body)

        # data output
        keys = r.json()
        print(keys["access_token"])

        self.headers = {
            "Client-ID": os.environ["TWITCH_CLIENT_ID"],
            "Authorization": "Bearer " + keys["access_token"],
        }

    def isLive(self, streamer_name):
        try:
            stream = requests.get(
                "https://api.twitch.tv/helix/streams?user_login=" + streamer_name,
                headers=self.headers,
            )

            stream_data = stream.json()
            print(stream_data)
            if "data" not in stream_data:
                self.login()
                stream = requests.get(
                    "https://api.twitch.tv/helix/streams?user_login=" + streamer_name,
                    headers=self.headers,
                )

                stream_data = stream.json()

            if len(stream_data["data"]) == 1:
                return True
            else:
                return False
        except:
            return False

    def getUsername(self, link: str):
        link.split("/")
        return link[-1]


player = Twitch()
username = "https://www.twitch.tv/usernname"
print(username)
result = player.isLive(username)

print(result)
