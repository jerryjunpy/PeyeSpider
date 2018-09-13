# coding: utf-8
from utils import user_agent, config
import time
import jsonpath
from utils.log import get_logger
from w3lib.html import remove_tags
import datetime
from urllib import parse
import hashlib
import requests
from lxml import etree
from requests.adapters import HTTPAdapter
import re
import execjs

logger = get_logger(__name__)
timestamp = int(round(time.time() * 10000))


class PeyeSpider(object):
    """
    网贷天眼
    """

    def __init__(self):
        self.headers = {"User-Agent": user_agent.UserAgent(mobile_ua=True)}
        self.url = 'https://www.p2peye.com/search.php?'
        self.title_hash = list()
        self.session = requests.session()
        # 超时自动重新请求3次
        max_retries = 3
        adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.session.keep_alive = False

    def _parse_js(self, script):
        js = script.replace("<script>", "", 1).split("while(z++)", 1)[0]
        js += r'function get_z(){return z}function get_y(z){return y.replace(/\b\w+\b/g, function (y) {return x[f(y, z) - 1] || ("_" + y)})}'

        ctx = execjs.compile(js)
        z = ctx.call("get_z")

        for i in range(10):
            y = ctx.call("get_y", z + i)
            if "setTimeout('location.href=" in y:
                return y
        else:
            raise Exception("解析js失败")

    @staticmethod
    def _parse_cookie(js):
        cookie_string, anonymous_function = re.search(
            r"(__jsl_clearance=\d+\.?\d+\|0\|)'\+(\(function\(\).+)\+';Expires=", js).groups()
        result = execjs.eval(anonymous_function)

        key, value = f"{cookie_string}{result}".split("=")
        return {key: value}

    def get_cookies(self, script):
        js = self._parse_js(script)
        return self._parse_cookie(js)

    def efactoring_cookie(self):

        for _ in config.keywords_list:
            payload = {
                "mod": "h5",
                "keywords": _,
                "ajax": "1",
                "page": "1",
            }
            first_res = self.session.get(self.url, headers=self.headers, params=payload)

            if first_res.status_code == 521:  # 网贷天眼经常改变网页规则，所以这里来了判断，如果是521就先解密
                cookie_dict = self.get_cookies(first_res.text)
                requests.utils.add_dict_to_cookiejar(self.session.cookies, cookie_dict)
                res = self.session.get(self.url, headers=self.headers, params=payload)
                self.main_crawler(res)

            elif first_res.status_code == 200:

                self.main_crawler(first_res)
            else:
                break

    def main_crawler(self, response):

        try:
            result = response.json()
            if result.get('message') == 'ok':
                article_list = jsonpath.jsonpath(result, "$...list")[0]

                for i in article_list:
                    if i.get('index') != 'post':  # 去除平台帖子
                        article_url = "https:" + i.get('url')
                        article_title = remove_tags(i.get('subject'))

                        hl = hashlib.md5()
                        hl.update(article_title.encode(encoding='utf-8'))
                        title_sign = hl.hexdigest()
                        if title_sign in self.title_hash:  # 根据标题去重
                            continue

                        self.title_hash.append(title_sign)
                        response = self.session.get(article_url, headers=self.headers)
                        if response.status_code == 200:
                            e = etree.HTML(response.text)
                            article_data = e.xpath(".//script[@type='application/ld+json']/text()")[0]
                            published_time = eval(article_data).get('pubDate').replace('T', ' ')

                            if published_time > datetime.datetime.today().strftime("%Y-%m-%d"):  # 当天的日期:
                                information_data = {
                                    "platform_name": "网贷天眼",
                                    "title_sign": title_sign,
                                    "published_time": published_time,
                                    "article_title": article_title,
                                    "article_url": article_url,
                                    "create_time": int(time.time())
                                }
                                print(information_data)
        except Exception as e:
            pass
            # logger.error(f"{'GET'} {self.url} headers={self.headers}")


def main():
    b = PeyeSpider()
    b.efactoring_cookie()


if __name__ == '__main__':
    main()
