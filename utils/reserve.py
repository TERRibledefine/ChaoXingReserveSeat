from utils import AES_Encrypt, enc, generate_captcha_key, verify_param
import json
from curl_cffi import requests
import re
import time
import logging
import datetime
import random


def get_date(day_offset: int = 0):
    today = datetime.datetime.now().date()
    offset_day = today + datetime.timedelta(days=day_offset)
    tomorrow = offset_day.strftime("%Y-%m-%d")
    return tomorrow


class reserve:
    def __init__(
        self,
        sleep_time=2,
        max_attempt=6,
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
        # 指纹可轮换：chrome120/chrome124/edge101
        self.requests = requests.Session(impersonate="chrome120")
        self.token_pattern = re.compile("token = '(.*?)'")
        
        # 主请求头（无硬编码Host）
        self.headers = {
            "Referer": "https://office.chaoxing.com/",
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
        # 登录请求头（统一UA，与主请求一致）
        self.login_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "accept-encoding": "gzip, deflate, br, zstd",
            "cache-control": "no-cache",
            "Connection": "keep-alive",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

        self.sleep_time = sleep_time
        self.max_attempt = max_attempt
        self.enable_slider = enable_slider
        self.reserve_next_day = reserve_next_day

    # 通用token提取（无固定UID）
    def _get_page_token(self, url, require_value=False):
        response = self.requests.get(url=url)
        html = response.content.decode("utf-8")
        match = re.search(r'([a-f0-9]{32}_\d{8,12})', html)
        if not match:
            logging.error(f"Failed to get token from {url}")
            return "", ""
        token = match.group(1)
        value = ""
        if require_value:
            value_match = re.search(r'value="([^"]+)"', html)
            if value_match:
                value = value_match.group(1)
        return token, value

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
            "refer": "https%3A%2F%2Foffice.chaoxing.com%2F",  # 根Referer，无固定座位
            "t": True,
        }
        jsons = self.requests.post(url=self.login_url, params=parm)
        obj = jsons.json()
        if obj["status"]:
            logging.info(f"User {username} login successfully")
            return (True, "")
        else:
            logging.info(
                f"User {username} login failed. Please check you password and username! "
            )
            return (False, obj["msg2"])

    def roomid(self, encode):
        url = f"https://office.chaoxing.com/data/apps/seat/room/list?cpage=1&pageSize=100&firstLevelName=&secondLevelName=&thirdLevelName=&deptIdEnc={encode}"
        json_data = self.requests.get(url=url).content.decode("utf-8")
        ori_data = json.loads(json_data)
        for i in ori_data["data"]["seatRoomList"]:
            info = f'{i["firstLevelName"]}-{i["secondLevelName"]}-{i["thirdLevelName"]} id为：{i["id"]}'
            print(info)

    # 获取验证码图片（动态Referer）
    def get_slide_captcha_data(self, current_url=None):
        url = "https://captcha.chaoxing.com/captcha/get/verification/image"
        timestamp = int(time.time() * 1000)
        capture_key, token = generate_captcha_key(timestamp)
        referer = current_url if current_url else "https://office.chaoxing.com/"
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
            "d": "a",
            "b": "a",
        }
        response = self.requests.get(url=url, params=params, headers=self.headers)
        content = response.text
        data = content.replace(callback + "(", "").replace(")", "")
        data = json.loads(data)
        captcha_token = data["token"]
        bg = data["imageVerificationVo"]["shadeImage"]
        tp = data["imageVerificationVo"]["cutoutImage"]
        return captcha_token, bg, tp

    # 解析验证码
    def resolve_captcha(self, current_url=None):
        logging.info(f"Start to resolve captcha token")
        captcha_token, bg, tp = self.get_slide_captcha_data(current_url)
        logging.info(f"Successfully get prepared captcha_token {captcha_token}")
        logging.info(f"Captcha Image URL-small {tp}, URL-big {bg}")
        x = self.x_distance(bg, tp)
        x = x + random.randint(-3, 3)
        logging.info(f"Successfully calculate the captcha distance {x}")

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
            f"https://captcha.chaoxing.com/captcha/check/verification/result",
            params=params,
            headers=self.headers,
        )
        text = response.text.replace(callback + "(", "").replace(")", "")
        data = json.loads(text)
        logging.info(f"Successfully resolve the captcha token {data}")
        try:
            validate_val = json.loads(data["extraData"])["validate"]
            return validate_val
        except KeyError as e:
            logging.info("Can't load validate value. Maybe server return mistake.")
            return ""

    # 计算滑块距离（无硬编码Host）
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
            cropped_image = slider_part[y : y + h, x : x + w]
            return cropped_image

        c_captcha_headers = {
            "Referer": "https://office.chaoxing.com/",
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
        bgc = self.requests.get(bg, headers=c_captcha_headers)
        tpc = self.requests.get(tp, headers=c_captcha_headers)
        bg, tp = bgc.content, tpc.content
        bg_img = cv2.imdecode(np.frombuffer(bg, np.uint8), cv2.IMREAD_COLOR)
        tp_img = cut_slide(tp)
        bg_edge = cv2.Canny(bg_img, 100, 200)
        tp_edge = cv2.Canny(tp_img, 100, 200)
        bg_pic = cv2.cvtColor(bg_edge, cv2.COLOR_GRAY2RGB)
        tp_pic = cv2.cvtColor(tp_edge, cv2.COLOR_GRAY2RGB)
        res = cv2.matchTemplate(bg_pic, tp_pic, cv2.TM_CCOEFF_NORMED)
        _, _, _, max_loc = cv2.minMaxLoc(res)
        tl = max_loc
        return tl[0]

    # 提交预约（含空token拦截）
    def submit(self, times, roomid, seatid, action):
        time.sleep(random.uniform(0.3, 1.2))
        for seat in seatid:
            suc = False
            attempt = self.max_attempt
            while not suc and attempt > 0:
                current_url = self.url.format(roomid, seat)
                token, value = self._get_page_token(current_url, require_value=True)
                if not token:
                    logging.warning("Empty token, retry after 2s")
                    time.sleep(2)
                    attempt -= 1
                    continue
                logging.info(f"Get token: {token}")
                captcha = self.resolve_captcha(current_url) if self.enable_slider else ""
                logging.info(f"Captcha token {captcha}")
                suc = self.get_submit(
                    self.submit_url,
                    times=times,
                    token=token,
                    roomid=roomid,
                    seatid=seat,
                    captcha=captcha,
                    action=action,
                    value=value,
                )
                if suc:
                    return suc
                time.sleep(random.uniform(0.5, 1.5))
                attempt -= 1
        return suc

    def get_submit(
        self, url, times, token, roomid, seatid, captcha="", action=False, value=""
    ):
        delta_day = 1 if self.reserve_next_day else 0
        day = datetime.date.today() + datetime.timedelta(days=0 + delta_day)
        if action:
            day = datetime.date.today() + datetime.timedelta(days=1 + delta_day)
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
        logging.info(f"submit parameter {parm} ")
        parm["enc"] = verify_param(parm, value)
        html = self.requests.post(url=url, params=parm).content.decode("utf-8")
        self.submit_msg.append(
            times[0] + "~" + times[1] + ":  " + str(json.loads(html))
        )
        logging.info(json.loads(html))
        return json.loads(html)["success"]