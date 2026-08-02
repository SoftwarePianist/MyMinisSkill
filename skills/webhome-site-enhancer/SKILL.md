---
name: webhome-site-enhancer
description: "根据用户提供的视频/新闻/影视/吃瓜类网站，生成适用 Minis/WebHome 的 WebHome 站源与原生播放注入扩展脚本。当用户要求“写一个 WebHome 扩展”、“增强网页版播放器”、“自动跳过分流/年龄验证/弹窗”、“把网站做成 WebHome 配置”或提供视频网站要求接入 Minis 客户端时触发。"
version: 1.0.0
---

# WebHome 站点增强与原生播放扩展生成流程 (WebHome Site Enhancer)

本技能提供从零分析网页、去除弹窗广告、提取视频接口并打包生成标准 WebHome 注入扩展（Site Config + Extension Code）的全流程规范。

---

## 1. 核心架构与协议契约

WebHome 扩展运行在 Minis WebView 内部，通过注入 `fm` SDK 实现原生增强。标准打包文件包含：
1. `site.json` / `site-inline.json`: WebHome 站源配置，包含站点基础信息与扩展代码。
2. `hlbdy.manifest.json` (模板名 `<site>.manifest.json`): 扩展描述清单。
3. `<site>.webhome.js`: ES5/ES6 兼容的注入脚本。

---

## 2. 标准制作流程 (Workflow)

```text
[阶段 1: 探测与抓包分析]
   ├── curl/browser_use 探测网页 URL 结构
   ├── 提取网页播放器数据配置 (如 dplayer / dp / video 节点的 data-config)
   └── 分析弹窗类型 (年龄验证 / APP引导弹窗 / 浮动广告)

[阶段 2: 前置首屏优化 (earlyBoot)]
   ├── 抢先注入 <style> CSS 强制隐藏所有弹窗 class/id (display:none !important)
   ├── localStorage 预填绕过年龄验证 (如 age-verify-date = 今日)
   └── 线路选择页自动静默重定向 (location.replace 避开分流中间页)

[阶段 3: 原生播放解析与交互]
   ├── 提取文章/详情页全部视频源 (m3u8/mp4)
   ├── 提取封面与元数据 (标题、集数、标签)
   └── 注入“原生 App 播放”按钮，触发 fm.vodInline(payload)

[阶段 4: 兼容性与网页播放器保护]
   ├── 播放器预加载定格: 纯被动监听 canplay 事件 seek(0.08) 并 pause()，绝不主动 load() 打断 hls.js
   └── ES2017 兼容写法 (不使用可选链 ?. / 回溯正则 / replaceAll)

[阶段 5: 配置打包与注入时机锁定]
   ├── 设置 runAt: "document-start" (确保抢在站点脚本之前注入 CSS)
   ├── 设置 cspKeyRegex: ["^<site-key>$"] 绑定站点 Key
   └── 生成 site-inline.json 单文件打包供用户导入
```

---

## 3. 核心功能脚本代码模板

### 3.1 前置拦截与静默跳转 (earlyBoot)

```js
(function earlyBoot() {
  // 1. 同步注入 CSS，抢在页面 DOM 渲染前压制所有弹窗
  try {
    var st = document.createElement("style");
    st.setAttribute("data-fm-early", "1");
    st.textContent = 
      "#age-verify-overlay,.age-verify-overlay{display:none!important;visibility:hidden!important;opacity:0!important;pointer-events:none!important;}"
      + "html.age-verify-locked,html.age-verify-locked body{overflow:auto!important;height:auto!important;}"
      + ".popup-container,.popup-content,.launchapp-btn-container{display:none!important;visibility:hidden!important;}"
      + "#adFloat,#aiFloat,.adspop,.application-popup,.popup-ad{display:none!important;}";
    (document.head || document.documentElement).appendChild(st);
  } catch (e0) {}

  // 2. 预填年龄验证 localStorage 缓存（按日期绕过）
  try {
    var d = new Date();
    var today = d.getFullYear() + "-" + (d.getMonth() + 1 < 10 ? "0" : "") + (d.getMonth() + 1) + "-" + (d.getDate() < 10 ? "0" : "") + d.getDate();
    if (window.localStorage && localStorage.getItem("age-verify-date") !== today) {
      localStorage.setItem("age-verify-date", today);
    }
  } catch (e) {}

  // 3. 分流线路页静默重定向
  try {
    if (/(^|\.)entry-domain\.com$/i.test(location.hostname)) {
      var cached = localStorage.getItem("fm-line-cache") || "https://real-site.com";
      location.replace(cached + (location.search || ""));
    }
  } catch (e) {}
})();
```

### 3.2 原生播放数据构建 (vodInline)

```js
function playNative(button) {
  whenFm().then(function (sdk) {
    var episodes = collectEpisodes(); // 提取页面上的 video m3u8
    if (!episodes.length) throw new Error("未找到视频地址");
    
    var payload = {
      vod_id: "site-" + location.pathname.replace(/\D+/g, ""),
      vod_name: pageTitle(),
      vod_pic: proxiedArtwork(firstContentImage()),
      vod_play_from: "专线",
      mark: episodes[0].name,
      headers: { Referer: location.href },
      credentials: "include",
      episodes: episodes
    };
    return sdk.vodInline(payload);
  });
}
```

### 3.3 网页播放器首帧定格 (纯被动模式)

```js
function primeWebPlayerFrames() {
  var videos = document.querySelectorAll(".dplayer video");
  for (var i = 0; i < videos.length; i++) {
    (function (video) {
      if (video.getAttribute("data-fm-first-frame") === "1") return;
      video.setAttribute("data-fm-first-frame", "1");

      // 仅当视频自己到达 canplay（hls.js 喂入数据）时 seek 到首帧定格
      // 严禁主动调用 video.load() 或操作 hls.startLoad()，避免打断 hls.js 状态机
      video.addEventListener("canplay", function () {
        if (video.getAttribute("data-fm-user-played") === "1") return;
        if (!video.paused || video.currentTime > 0.25) return;
        try {
          video.currentTime = 0.08;
          video.pause();
        } catch (e) {}
      }, { once: true });

      video.addEventListener("play", function () {
        video.setAttribute("data-fm-user-played", "1");
      }, { once: true });
    })(videos[i]);
  }
}
```

---

## 4. 关键踩坑与质量要求 (Critical Guidelines)

1. **注入时机严格设置为 `runAt: "document-start"`**：只有在文档刚创建时注入，才能靠 CSS 压制弹窗。`document-end` 会导致弹窗一闪而过。
2. **严禁干预 hls.js 加载状态机**：绝不主动 `load()`、绝不重写 `hls.prototype.attachMedia`，网页端加载完全由原站播放器自理。
3. **域名作用域必须全覆盖**：`site-inline.json` / `site.json` / `manifest.json` 三个配置中的 `runAt` 必须统一为 `"document-start"`，`cspKeyRegex` 必须包含站点 Key。
4. **输出物要求**：每次生成必须提供可直接在 App 导入的 `site-inline.json` minis 链接。
