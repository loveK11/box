# box — 嗷呜 TVBox 接口自动更新

源接口：`http://www.嗷呜.cc/tv`（嗷呜主接口，备用接口见该站首页的 `assets/apis.json`）

每天北京时间 10:00 自动拉取并解密一次，解密后的配置保存在 `aowu.json` 里，源接口没变就不提交，变了就自动更新。

## 在 TVBox / OK影视 里怎么用

配置地址填：

```
https://raw.githubusercontent.com/loveK11/box/main/aowu.json
```

今天（2026-11-25）解密出来的内容：84 个点播源、7 个直播源（综合直播、咖啡体育、虎牙一起看、斗鱼一起看、B站直播、YY轮播等）、2 个解析。

## spider 本地包

`aowu.json` 里的 `spider` 不再指向源站的网易云图片地址，改成本地包：

```
"spider": "aw.png;md5;f33fe0621341289e1491f2ae55b4423b"
```

`aw.png` 就在仓库根目录，和 `aowu.json` 在一起，TVBox 按相对路径就能找到它。这个文件其实不是图片，是伪装成 `.png` 的 spider 包（jar），下载下来 md5 和配置里写的一致。

扩展名是按 spider 地址定的：地址后边是 `.png` 就存成 `aw.png`，是 `.jar` 就存成 `aw.jar`，每次同步都重新判断，扩展名变了就把旧的 `aw.*` 删掉，`aowu.json` 里的 spider 也跟着改。

## 它是怎么更新的

仿照 [qist/tvbox](https://github.com/qist/tvbox) 的 `run.yml` 做的：

- `tools/tvbox.py` 就是 qist 仓库里的解密工具：用 `okhttp/3.12.0` 去请求 `/tv`，源站会 302 到一张网易云图片，配置 JSON 以 base64 藏在图片里，工具把它取出来解成 JSON。
- `scripts/sync_aowu.py` 是同步脚本：先调 `tvbox.py` 解密并校验（有点播源、spider 才算成功）；解密失败时改用嗷呜自己的解密接口 `POST https://www.嗷呜.cc/api/decode.php` 再试一次；两次都失败就让 Action 报错，不会提交坏文件。解密完还会把 spider 文件下载到本地，按 spider 地址的扩展名存成 `aw.png` 或 `aw.jar`，并把 `aowu.json` 里的 spider 改成本地名。
- `.github/workflows/sync-aowu.yml` 是定时任务：每天 02:00 UTC（北京时间 10:00）跑一次，也可以在仓库 Actions 页面手动点 `Run workflow` 立即跑一次。

## 本地自己跑（可选）

```bash
pip install pycryptodome
python3 scripts/sync_aowu.py aowu.json
```

## 说明

本仓库只做接口的自动同步和解密，配置内容来自嗷呜源站，版权归源站和各源作者所有，仅供学习研究使用。
