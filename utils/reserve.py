from utils import AES_Encrypt, enc, generate_captcha_key, verify_param
import json
from curl_cffi import requests
import re
import time
import logging
import datetime
import random
from urllib3.exceptions import InsecureRequestWarning

# 关闭SSL警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_date(day_offset: int = 0):
    today = datetime.datetime.now().date()
    offset_day = today + datetime.timedelta(days=day_offset)
    return offset_day.strftime("%Y-%m-%d")


class reserve:
    def __init__(
        self,
        sleep_time=0.5,
        max_attempt=10,
        enable_slider=False,
        reserve_next_day=False,
    ):
        self.login_page = (
            "https://passport2.chaoxing.com/mlogin?loginType=1&newversion=true&fid="
        )
        self.url = (
            "https://office.chaoxing.com/front/third/apps/seat/code?id={}&seatNum={}"
        )
        self.submit_url = "https://office.chaoxing.com/data/apps/seat/submit"
        self.seat_url = "https://office.chaoxing.com/data/apps/seat/getusedtimes"
        self.login_url = "https://passport2.chaoxing.com/fanyalogin"
        self.token = ""
        self.success_times = 0
        self.fail_dict = []
        self.submit_msg = []
        
        # 保留curl_cffi的浏览器模拟，对抗反爬
        self.requests = requests.Session(impersonate="chrome120", verify=False)
        self.headers = {
            "Referer": "https://office.chaoxing.com/",
            "Host": "captcha.chaoxing.com",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Google Chrome";v="120", "Chromium";v="120", "Not.A/Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        self.login_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "accept-encoding": "gzip, deflate, br, zstd",
            "cache-control": "no-cache",
            "Connection": "keep-alive",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Host": "passport2.chaoxing.com",
        }

        self.sleep_time = sleep_time
        self.max_attempt = max_attempt
        self.enable_slider = enable_slider
        self.reserve_next_day = reserve_next_day

    # ✅ 核心修复：使用正确的submit_enc正则匹配Token
    def _get_page_token(self, url, require_value=False):
        response = self.requests.get(url=url)
        html = response.content.decode("utf-8")
        
        # 匹配当前超星页面的真实Token位置：id="submit_enc"的value值
        matches = re.findall(r'id="submit_enc"\s+value="(.*?)"', html)
        value_matches = None
        
        if require_value:
            value_matches = re.findall(r'name="enc"\s+value="(.*?)"', html)
            if not matches:
                logging.error(f"Failed to get token from {url}")
                return "", ""
            if not value_matches:
                logging.error(f"Failed to get submit value from {url}")
                return matches[0], ""
        
        return matches[0] if matches else "", value_matches[0] if value_matches else ""

    def get_login_status(self):
        self.requests.headers = self.login_headers
        self.requests.get(url=self.login_page)

    def login(self, username, password):
        username = AES_Encrypt(username)
        password = AES_Encrypt(password)
        parm = {
            "fid": -1,
            "uname": username,
            "password": password,
            "refer": "http%3A%2F%2Foffice.chaoxing.com%2Ffront%2Fthird%2Fapps%2Fseat%2Fcode%3Fid%3D4219%26seatNum%3D380",
            "t": True,
        }
        jsons = self.requests.post(url=self.login_url, params=parm)
        obj = jsons.json()
        if obj["status"]:
            logging.info(f"User {username} login successfully")
            return (True, "")
        else:
            logging.info(f"User {username} login failed: {obj['msg2']}")
            return (False, obj["msg2"])

    def roomid(self, encode):
        url = f"https://office.chaoxing.com/data/apps/seat/room/list?cpage=1&pageSize=100&firstLevelName=&secondLevelName=&thirdLevelName=&deptIdEnc={encode}"
        json_data = self.requests.get(url=url).content.decode("utf-8")
        ori_data = json.loads(json_data)
        for i in ori_data["data"]["seatRoomList"]:
            print(f'{i["firstLevelName"]}-{i["secondLevelName"]}-{i["thirdLevelName"]} id: {i["id"]}')

    # ✅ 保留随机callback，避免硬编码被反爬检测
    def resolve_captcha(self):
        logging.info("Start resolving captcha")
        captcha_token, bg, tp = self.get_slide_captcha_data()
        logging.info(f"Captcha token: {captcha_token}")
        
        x = self.x_distance(bg, tp)
        x = x + random.randint(-2, 2)  # 增加随机偏移，模拟人类操作
        logging.info(f"Calculated captcha distance: {x}")

        # 随机生成callback，防止被反爬识别
        callback = f"jQuery{random.randint(100000000, 999999999)}_{int(time.time() * 1000)}"
        params = {
            "callback": callback,
            "captchaId": "42sxgHoTPTKbt0uZxPJ7ssOvtXr3ZgZ1",
            "type": "slide",
            "token": captcha_token,
            "textClickArr": json.dumps([{"x": x}]),
            "coordinate": json.dumps([]),
            "runEnv": "10",
            "version": "1.1.18",
            "_": int(time.time() * 1000),
        }
        response = self.requests.get(
            "https://captcha.chaoxing.com/captcha/check/verification/result",
            params=params,
            headers=self.headers,
        )
        # 正确解析JSONP响应
        text = response.text.replace(f"{callback}(", "").rstrip(")")
        data = json.loads(text)
        
        try:
            return json.loads(data["extraData"])["validate"]
        except KeyError:
            logging.error("Captcha validation failed")
            return ""

    # ✅ 修复JSONP解析的字符串替换错误
    def get_slide_captcha_data(self):
        url = "https://captcha.chaoxing.com/captcha/get/verification/image"
        timestamp = int(time.time() * 1000)
        capture_key, token = generate_captcha_key(timestamp)
        referer = "https://office.chaoxing.com/front/third/apps/seat/code?id=3993&seatNum=0199"
        
        callback = f"jQuery{random.randint(100000000, 999999999)}_{timestamp}"
        params = {
            "callback": callback,
            "captchaId": "42sxgHoTPTKbt0uZxPJ7ssOvtXr3ZgZ1",
            "type": "slide",
            "version": "1.1.18",
            "captchaKey": capture_key,
            "token": token,
            "referer": referer,
            "_": timestamp,
        }
        response = self.requests.get(url=url, params=params, headers=self.headers)
        content = response.text

        # ✅ 修复这里的替换错误：原来的代码错误地替换成了")"
        data = content.replace(f"{callback}(", "").rstrip(")")
        data = json.loads(data)
        
        return (
            data["token"],
            data["imageVerificationVo"]["shadeImage"],
            data["imageVerificationVo"]["cutoutImage"]
        )

    def x_distance(self, bg, tp):
        import numpy as np
        import cv2

        def cut_slide(slide):
            slider_array = np.frombuffer(slide, np.uint8)
            slider_image = cv2.imdecode(slider_array, cv2.IMREAD_UNCHANGED)
            slider_part = slider_image[:, :, :3]
            mask = slider_image[:, :, 3]
            mask[mask != 0] = 255
            x, y, w, h = cv2.boundingRect(mask)
            return slider_part[y : y + h, x : x + w]

        c_captcha_headers = {
            "Referer": "https://office.chaoxing.com/",
            "Host": "captcha-b.chaoxing.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        bgc = self.requests.get(bg, headers=c_captcha_headers)
        tpc = self.requests.get(tp, headers=c_captcha_headers)
        
        bg_img = cv2.imdecode(np.frombuffer(bgc.content, np.uint8), cv2.IMREAD_COLOR)
        tp_img = cut_slide(tpc.content)
        
        # 边缘检测+模板匹配
        bg_edge = cv2.Canny(bg_img, 100, 200)
        tp_edge = cv2.Canny(tp_img, 100, 200)
        res = cv2.matchTemplate(bg_edge, tp_edge, cv2.TM_CCOEFF_NORMED)
        _, _, _, max_loc = cv2.minMaxLoc(res)
        
        return max_loc[0]

    def submit(self, times, roomid, seatid, action=False):
        for seat in seatid:
            attempt = 0
            while attempt < self.max_attempt:
                token, value = self._get_page_token(
                    self.url.format(roomid, seat), require_value=True
                )
                logging.info(f"Seat {seat} Token: {token}")
                
                captcha = self.resolve_captcha() if self.enable_slider else ""
                success = self.get_submit(
                    times=times,
                    token=token,
                    roomid=roomid,
                    seatid=seat,
                    captcha=captcha,
                    action=action,
                    value=value,
                )
                
                if success:
                    logging.info(f"Seat {seat} reserve success!")
                    return True
                
                attempt += 1
                time.sleep(random.uniform(0.3, 1.0))
        
        logging.error("All seats reserve failed")
        return False

    def get_submit(self, times, token, roomid, seatid, captcha="", action=False, value=""):
        delta_day = 1 if self.reserve_next_day else 0
        day = datetime.date.today() + datetime.timedelta(days=delta_day)
        if action:
            day += datetime.timedelta(days=1)

        parm = {
            "roomId": roomid,
            "startTime": times[0],
            "endTime": times[1],
            "day": str(day),
            "seatNum": seatid,
            "captcha": captcha,
            "token": token,
            "type": "1",
            "verifyData": "1",
        }
        parm["enc"] = verify_param(parm, value)
        
        response = self.requests.post(url=self.submit_url, params=parm)
        result = response.json()
        self.submit_msg.append(f"{times[0]}~{times[1]}: {result}")
        logging.info(f"Submit result: {result}")
        
        return result["success"]
