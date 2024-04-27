import json

def load_api_key(key):
    with open('../.config', 'r') as file:
        config = json.load(file)
        return config[key]

if __name__ == '__main__':
    print(load_api_key('stratechery_email'))