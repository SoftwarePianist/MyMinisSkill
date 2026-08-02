# -*- coding: utf-8 -*-
"""
TVBox/CatVod 影视爬虫插件模板
根据目标网站的特性进行调整。
"""

import re
import json
import urllib.parse
import threading
import requests
import random

try:
    from Crypto.Cipher import AES
except ImportError:
    AES = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass

class Spider(BaseSpider):
    # 默认域名，如果是动态字典域名请自行编写 get_latest_domain()
    BASE_URL = "https://example.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
    }
    
    def __init__(self):
        super().__init__()
        self.name = "SpiderName"
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.session.verify = False 
        
        # 本地代理配置（用于破解图片防盗链或AES加密图片，不需要可删除）
        self.proxy_port = 9980
        self._proxy_started = False
        # self._start_image_proxy()

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend)
                base_url = cfg.get("base_url") or cfg.get("site")
                if base_url:
                    self.BASE_URL = base_url.rstrip("/")
            except:
                pass
        return None

    def getName(self):
        return self.name

    def homeContent(self, filter):
        result = {
            "class": [],
            "filters": {},
            "list": [],
            "parse": 0,
            "jx": 0,
        }
        
        # 构建两级分类菜单（支持 TVBox 高级筛选）
        # 注意：包含 filters 会使 TVBox 进入高级排版模式，要求 list 中的 vod_year/vod_actor 等字段必须存在才能显示轮播图
        result["class"] = [
            {"type_id": "home", "type_name": "首页"},
            {"type_id": "cat1", "type_name": "分类一"}
        ]
        
        result["filters"] = {
            "cat1": [{"key": "sub", "name": "子分类", "value": [
                {"n": "子类A", "v": "subA"},
                {"n": "子类B", "v": "subB"}
            ]}]
        }
        
        try:
            r = self.session.get(self.BASE_URL + "/", timeout=15)
            r.encoding = 'utf-8'
            result["list"] = self._parse_list(r.text)
        except Exception as e:
            print(f"homeContent error: {e}")
            
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {
            "page": int(pg),
            "pagecount": 999, # 填 999 强制开启 TVBox 无限下拉翻页
            "limit": 20,
            "total": 9999,    # 虚假总数，骗过 TVBox 翻页检查
            "list": [],
            "parse": 0,
            "jx": 0,
        }
        try:
            real_tid = extend["sub"] if (extend and "sub" in extend) else tid
            
            # TODO: 根据目标网站填写分页规则
            if real_tid == "home":
                url = f"{self.BASE_URL}/" if str(pg) == "1" else f"{self.BASE_URL}/page/{pg}/"
            else:
                url = f"{self.BASE_URL}/category/{real_tid}/" if str(pg) == "1" else f"{self.BASE_URL}/category/{real_tid}/{pg}/"
                
            r = self.session.get(url, timeout=15)
            r.encoding = 'utf-8'
            result["list"] = self._parse_list(r.text)
            result["pagecount"] = int(pg) if not result["list"] else int(pg) + 1
        except Exception as e:
            print(f"categoryContent error: {e}")
        return result

    def detailContent(self, ids):
        result = {"list": [], "parse": 0, "jx": 0}
        try:
            vid = str(ids[0])
            url = f"{self.BASE_URL}/archives/{vid}/"
            r = self.session.get(url, timeout=15)
            r.encoding = 'utf-8'
            html = r.text
            
            # TODO: 解析标题、封面、简介、关键词
            title = vid
            cover = ""
            content = ""
            remarks = "播放"
            
            # TODO: 提取 M3U8/MP4 播放地址（注意单网页多视频支持）
            urls = []
            
            play_parts = []
            for idx, u in enumerate(urls, 1):
                ep_name = f"视频{idx}" if len(urls) > 1 else "播放"
                play_parts.append(f"{ep_name}${u}")
            vod_play_url = "#".join(play_parts)
            
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": cover,
                "type_name": "分类",
                "vod_year": "2026",      # 必须填假数据以兼容轮播图
                "vod_area": "中国",
                "vod_remarks": remarks,
                "vod_actor": "网友",     # 必须填假数据以兼容轮播图
                "vod_director": "管理员", # 必须填假数据以兼容轮播图
                "vod_content": content,
                "vod_play_from": self.name,
                "vod_play_url": vod_play_url,
            }
            result["list"].append(vod)
        except Exception as e:
            print(f"detailContent error: {e}")
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {
            "page": int(pg), "pagecount": 999, "limit": 20, "total": 9999,
            "list": [], "parse": 0, "jx": 0,
        }
        try:
            k = urllib.parse.quote(key)
            url = f"{self.BASE_URL}/search/{k}/" if str(pg) == "1" else f"{self.BASE_URL}/search/{k}/{pg}/"
            r = self.session.get(url, timeout=15)
            r.encoding = 'utf-8'
            result["list"] = self._parse_list(r.text)
            result["pagecount"] = int(pg) if not result["list"] else int(pg) + 1
        except Exception as e:
            print(f"searchContent error: {e}")
        return result

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "jx": 0,
            "header": {
                "User-Agent": self.HEADERS["User-Agent"],
                "Referer": self.BASE_URL + "/",
            },
        }

    def _parse_list(self, html):
        vod_list = []
        # TODO: 从列表页 HTML 提取视频列表
        articles = re.findall(r'<article[^>]*>([\s\S]*?)</article>', html)
        for art in articles:
            url_match = re.search(r'href="/archives/(\d+)/"', art)
            if not url_match: continue
            vid = url_match.group(1)
            
            # TODO: 提取标题和封面，清理干扰标签
            title = ""
            cover = ""
            
            vod_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": cover,
                "vod_remarks": "热播",
                "vod_year": "2026", # 兼容轮播图
            })
        return vod_list