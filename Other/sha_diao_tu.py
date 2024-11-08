
import requests

class FreeApi:
    def __init__(self):
        self.api_url = 'https://way.jd.com/showapi/dtgxt?page=1&maxResult=20&appkey=da39dce4f8aa52155677ed8cd23a6470'

    def get_result(self):
        response = requests.get(self.api_url)
        if response.status_code == 200:
            return response.json()
        else:
            return {'error': 'Failed to fetch data', 'status_code': response.status_code}

# 使用示例
if __name__ == "__main__":
    api = FreeApi()
    result = api.get_result()
    print(result)