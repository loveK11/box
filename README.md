# box — 嗷呜 TVBox 接口自动更新

源接口：`http://www.嗷呜.cc/tv`（嗷呜主接口，备用接口见该站首页的 `assets/apis.json`）

每天北京时间 10:00 自动拉取并解密一次，解密后的配置保存在 `aowu.json` 里，源接口没变就不提交，变了就自动更新。

## 在 TVBox / OK影视 里怎么用

配置地址填：

```
https://raw.githubusercontent.com/loveK11/box/main/aowu.json
```

今天（2026-11-25）解密出来的内容：84 个点播源、7 个直播源（综合直播、咖啡体育、虎牙一起看、斗鱼一起看、B站直播、YY轮播等）、2 个解析。

## 本地包（按 bjq 编辑器“下载本地包”的逻辑分类）

`aowu.json` 里能下载的远程文件都下了本地，按类型分文件夹，配置里改成相对路径：

```
jar/aw.png            # spider，名字固定 aw.*，扩展名按 spider 地址定
                      # （.png 就 aw.png，.jar 就 aw.jar）
img/EC508FBD....gif   # logo 图片
ext/4AFC77E5....aowu  # 点播源的 ext 文件（.aowu / .gz），共 7 个
lib/huyayqk.m3u       # 直播源的 m3u，共 5 个
lib/douyuyqk.m3u
lib/iptv.m3u
lib/bililive.m3u
lib/yylunbo.m3u
```

`aowu.json` 里的写法：

```
"spider": "./jar/aw.png;md5;f33fe0621341289e1491f2ae55b4423b"
"logo": "./img/EC508FBD046D33EC4832BB76B63B6C94.gif"
"ext": {"json": "./ext/4AFC77E563EDEDB37F18BA6458610E16.aowu", ...}
"lives": [{"name": "虎牙一起看", "url": "./lib/huyayqk.m3u"}, ...]
```

`aw.png` 其实不是图片，是伪装成 `.png` 的 spider 包（jar），下载下来 md5 和配置里写的一致。扩展名变了就把旧的 `aw.*` 删掉，`aowu.json` 里的 spider 也跟着改。

不下载、保持远程地址的：`127.0.0.1` 本地地址（弹幕、壁纸）、解析和 DoH 接口地址（没有文件名，下不了）、没有 m3u 地址的直播源（综合直播的 iptv.php、咖啡体育）。某个文件下载失败时只警告、保留远程地址，不会让整个同步失败；spider 下载失败才会报错。

## 它是怎么更新的

仿照 [qist/tvbox](https://github.com/qist/tvbox) 的 `run.yml` 做的：

- `tools/tvbox.py` 就是 qist 仓库里的解密工具：用 `okhttp/3.12.0` 去请求 `/tv`，源站会 302 到一张网易云图片，配置 JSON 以 base64 藏在图片里，工具把它取出来解成 JSON。
- `scripts/sync_aowu.py` 是同步脚本：先调 `tvbox.py` 解密并校验（有点播源、spider 才算成功）；解密失败时改用嗷呜自己的解密接口 `POST https://www.嗷呜.cc/api/decode.php` 再试一次；两次都失败就让 Action 报错，不会提交坏文件。解密完还会把配置里的远程文件按本地包逻辑分类下载：spider 存 `jar/aw.png`（或 `aw.jar`），图片存 `img/`，点播源的 ext 文件存 `ext/`，直播源的 m3u 存 `lib/`，并把 `aowu.json` 里的地址改成相对路径；下不了的文件（本地地址、解析接口、没有 m3u 地址的直播源）保持远程地址。
- `.github/workflows/sync-aowu.yml` 是定时任务：每天 02:00 UTC（北京时间 10:00）跑一次，也可以在仓库 Actions 页面手动点 `Run workflow` 立即跑一次。

## 本地自己跑（可选）

```bash
pip install pycryptodome
python3 scripts/sync_aowu.py aowu.json
```

## 说明

本仓库只做接口的自动同步和解密，配置内容来自嗷呜源站，版权归源站和各源作者所有，仅供学习研究使用。
