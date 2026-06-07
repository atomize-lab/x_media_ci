// Local screen: independent download on the phone.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:http/http.dart' as http;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:pdf/widgets.dart' as pw;
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import '../api/ci_api.dart';

class LocalScreen extends StatefulWidget {
  const LocalScreen({super.key});

  @override
  State<LocalScreen> createState() => _LocalScreenState();
}

class _LocalScreenState extends State<LocalScreen> {
  final _url = TextEditingController();
  String? _appDocsDir;

  @override
  void initState() {
    super.initState();
    _resolveDocs();
  }

  Future<void> _resolveDocs() async {
    try {
      Directory d;
      if (Platform.isAndroid) {
        d = (await getExternalStorageDirectory()) ?? await getApplicationDocumentsDirectory();
      } else {
        d = await getApplicationDocumentsDirectory();
      }
      if (!mounted) return;
      setState(() => _appDocsDir = d.path);
    } catch (_) {
      // path_provider is not supported on every desktop; ignore.
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          "Local sandbox: ${_appDocsDir ?? '(resolving...)'}",
          style: const TextStyle(fontFamily: "monospace"),
        ),
        const SizedBox(height: 12),
        const Text("输入推文 URL，在手机本地落盘：tweet.json / media / md / pdf。"),
        const SizedBox(height: 12),
        TextField(
          controller: _url,
          decoration: const InputDecoration(
            labelText: "Tweet URL",
            hintText: "https://x.com/<handle>/status/<id>",
          ),
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          icon: const Icon(Icons.download),
          label: const Text("打开网页并抓取"),
          onPressed: _appDocsDir == null
              ? null
              : () {
                  final u = _url.text.trim();
                  if (u.isEmpty) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text("请先粘贴推文 URL")),
                    );
                    return;
                  }
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => _LocalCaptureScreen(
                        url: u,
                        baseDir: _appDocsDir!,
                      ),
                    ),
                  );
                },
        ),
      ],
    );
  }
}

class _LocalCaptureScreen extends StatefulWidget {
  final String url;
  final String baseDir;
  const _LocalCaptureScreen({required this.url, required this.baseDir});

  @override
  State<_LocalCaptureScreen> createState() => _LocalCaptureScreenState();
}

class _LocalCaptureScreenState extends State<_LocalCaptureScreen> {
  final _log = <String>[];
  InAppWebViewController? _web;
  bool _busy = false;
  Key _webKey = UniqueKey();
  void Function(FlutterErrorDetails details)? _prevFlutterOnError;
  void Function(FlutterErrorDetails details)? _installedFlutterOnError;
  bool Function(Object error, StackTrace stack)? _prevPlatformOnError;

  String _url = "";
  String _handle = "";
  String _tweetId = "";
  String _dtUtc = "";
  String _text = "";

  final _imageUrls = <String>{};
  final _videoUrls = <String, Map<String, Set<String>>>{};
  DateTime? _videoCaptureUntil;

  bool get _videoCaptureActive =>
      _videoCaptureUntil != null && DateTime.now().isBefore(_videoCaptureUntil!);

  void _startVideoCaptureWindow() {
    setState(() {
      _videoUrls.clear();
      _videoCaptureUntil = DateTime.now().add(const Duration(seconds: 18));
    });
    _pushLog("[cap] cleared videos; now tap Play once to let WebView request mp4 URLs");
    Future.delayed(const Duration(seconds: 19), () {
      if (!mounted) return;
      if (_videoCaptureUntil != null && !_videoCaptureActive) {
        _pushLog("[cap] done videos=${_videoUrls.length}");
      }
    });
  }

  void _recreateWebView({String reason = ""}) {
    setState(() {
      _web = null;
      _webKey = UniqueKey();
    });
    _pushLog("[web] recreate${reason.isEmpty ? '' : ' ($reason)'}");
  }

  Future<void> _debugPageBasics() async {
    final c = _web;
    if (c == null) return;
    try {
      final raw = await c.evaluateJavascript(
        source:
            "JSON.stringify({href: location.href, title: document.title || '', ready: document.readyState || '', articles: (document.querySelectorAll('article') || []).length})",
      );
      final m = jsonDecode(raw.toString());
      if (m is Map) {
        final href = (m["href"] ?? "").toString();
        final ready = (m["ready"] ?? "").toString();
        final articles = (m["articles"] ?? "").toString();
        final t0 = (m["title"] ?? "").toString().trim();
        final title = t0.length > 60 ? "${t0.substring(0, 60)}…" : t0;
        _pushLog("[page] ready=$ready articles=$articles title=$title");
        if (href.isNotEmpty) _pushLog("[page] url=$href");
      }
    } catch (e) {
      _pushLog("[page] error: $e");
    }
  }

  void _observeUrl(String url) {
    if (url.contains("pbs.twimg.com/media/") ||
        url.contains("pbs.twimg.com/tweet_video_thumb/") ||
        url.contains("pbs.twimg.com/ext_tw_video_thumb/")) {
      final norm = _pbsToOrig(url);
      final before = _imageUrls.length;
      _imageUrls.add(norm);
      if (_imageUrls.length != before) {
        if (_imageUrls.length <= 2) {
          _pushLog("[img] + ${_imageUrls.length} $norm");
        } else if (_imageUrls.length == 3) {
          _pushLog("[img] + more… total=${_imageUrls.length}");
        } else {
          setState(() {});
        }
      }
      return;
    }
    if (url.contains("video.twimg.com/")) {
      if (!_videoCaptureActive) return;
      final k = _videoGroupKey(url);
      final g = _videoUrls.putIfAbsent(k, () => {"mp4": <String>{}, "m3u8": <String>{}});
      final before = (g["mp4"]!.length + g["m3u8"]!.length);
      if (url.contains(".m3u8")) {
        g["m3u8"]!.add(url);
      } else if (url.contains(".mp4")) {
        g["mp4"]!.add(url);
      }
      final after = (g["mp4"]!.length + g["m3u8"]!.length);
      if (after != before && (g["mp4"]!.length + g["m3u8"]!.length) == 1) {
        _pushLog("[vid] + group=$k");
      } else if (after != before) {
        setState(() {});
      }
    }
  }

  void _pushLog(String s) {
    setState(() {
      _log.add(s);
      if (_log.length > 300) {
        _log.removeRange(0, _log.length - 300);
      }
    });
  }

  Future<void> _copyLogs() async {
    final text = _log.join("\n");
    await Clipboard.setData(ClipboardData(text: text));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text("已复制日志到剪贴板")),
    );
  }

  @override
  void initState() {
    super.initState();
    _url = widget.url.trim();
    final parsed = _parseTweetUrl(_url);
    _handle = parsed.$1;
    _tweetId = parsed.$2;
    _prevFlutterOnError = FlutterError.onError;
    _installedFlutterOnError = (details) {
      final msg = details.exceptionAsString();
      _pushLog("[err] $msg");
      final lib = details.library ?? "";
      if (lib.isNotEmpty) _pushLog("[err] lib=$lib");
      final ctx = details.context?.toDescription() ?? "";
      if (ctx.isNotEmpty) _pushLog("[err] ctx=$ctx");
      _prevFlutterOnError?.call(details);
    };
    FlutterError.onError = _installedFlutterOnError;
    _prevPlatformOnError = ui.PlatformDispatcher.instance.onError;
    ui.PlatformDispatcher.instance.onError = (error, stack) {
      _pushLog("[err] $error");
      return _prevPlatformOnError?.call(error, stack) ?? false;
    };
    Future.delayed(const Duration(seconds: 2), () {
      if (!mounted) return;
      if (_web == null) {
        _pushLog("[web] not created (possible missing/disabled Android System WebView or Chrome)");
      }
    });
  }

  @override
  void dispose() {
    if (FlutterError.onError == _installedFlutterOnError) {
      FlutterError.onError = _prevFlutterOnError;
    }
    ui.PlatformDispatcher.instance.onError = _prevPlatformOnError;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final canSave = _tweetId.isNotEmpty && !_busy;
    return Scaffold(
      appBar: AppBar(
        title: const Text("Local Capture"),
        actions: [
          IconButton(
            icon: const Icon(Icons.copy_all),
            onPressed: _copyLogs,
          ),
          IconButton(
            icon: const Icon(Icons.save),
            onPressed: canSave ? _saveAll : null,
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _url,
                  style: const TextStyle(fontFamily: "monospace", fontSize: 12),
                ),
                const SizedBox(height: 6),
                Text(
                  "提示：首次请在此网页里登录 x.com；有视频请点一下播放，方便抓到 video 链接。",
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 6),
                Text(
                  "web=${_web != null}  images=${_imageUrls.length}  videos=${_videoUrls.length}  busy=$_busy",
                  style: const TextStyle(fontFamily: "monospace", fontSize: 12),
                ),
              ],
            ),
          ),
          Expanded(
            child: InAppWebView(
              key: _webKey,
              initialUrlRequest: URLRequest(url: WebUri("https://x.com/")),
              initialSettings: InAppWebViewSettings(
                javaScriptEnabled: true,
                domStorageEnabled: true,
                mediaPlaybackRequiresUserGesture: true,
                allowsInlineMediaPlayback: true,
                sharedCookiesEnabled: true,
                thirdPartyCookiesEnabled: true,
                useShouldInterceptRequest: true,
                userAgent:
                    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36",
              ),
              onWebViewCreated: (c) async {
                _web = c;
                _pushLog("[web] created");
                await _prepareAndLoad();
              },
              onLoadStart: (c, u) {
                final s = u?.toString() ?? "";
                if (s.isNotEmpty) _pushLog("[web] start $s");
              },
              onLoadStop: (c, _) async {
                await _debugPageBasics();
                await _extractFromDom();
              },
              onLoadError: (c, _, code, msg) {
                _pushLog("[web] load error code=$code msg=$msg");
              },
              onLoadHttpError: (c, _, statusCode, description) {
                _pushLog("[web] http error code=$statusCode $description");
              },
              onLoadResource: (c, res) {
                _observeUrl(res.url.toString());
              },
              shouldInterceptRequest: (c, req) async {
                final u = req.url?.toString() ?? "";
                if (u.isNotEmpty) {
                  _observeUrl(u);
                }
                return null;
              },
            ),
          ),
          SizedBox(
            height: 180,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
              children: [
                for (final s in _log.reversed.take(12))
                  SelectableText(
                    s,
                    style: const TextStyle(fontFamily: "monospace", fontSize: 11),
                  ),
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        icon: const Icon(Icons.refresh),
        label: const Text("刷新提取"),
        onPressed: _busy
            ? null
            : () async {
                if (_web == null) {
                  _recreateWebView(reason: "controller is null");
                  return;
                }
                _startVideoCaptureWindow();
                await _extractFromDom();
              },
      ),
    );
  }

  Future<void> _prepareAndLoad() async {
    final c = _web;
    if (c == null) return;
    await _applyXCookies();
    await c.loadUrl(urlRequest: URLRequest(url: WebUri(_url)));
  }

  Future<void> _applyXCookies() async {
    final auth = CiApi.instance.xAuthToken;
    final ct0 = CiApi.instance.xCt0;
    if (auth.isEmpty || ct0.isEmpty) {
      _pushLog("[cookie] no auth_token/ct0 (will rely on web login)");
      return;
    }
    try {
      final cm = CookieManager.instance();
      await cm.setCookie(
        url: WebUri("https://x.com/"),
        name: "auth_token",
        value: auth,
        domain: ".x.com",
        path: "/",
        isHttpOnly: true,
        isSecure: true,
      );
      await cm.setCookie(
        url: WebUri("https://x.com/"),
        name: "ct0",
        value: ct0,
        domain: ".x.com",
        path: "/",
        isHttpOnly: false,
        isSecure: true,
      );
      _pushLog("[cookie] injected auth_token + ct0");
    } catch (e) {
      _pushLog("[cookie] inject failed: $e");
    }
  }

  Future<void> _extractFromDom() async {
    final c = _web;
    if (c == null) {
      _pushLog("[extract] webview not ready");
      _recreateWebView(reason: "extract called before created");
      return;
    }
    try {
      final js = """
(() => {
  const tid = ${jsonEncode(_tweetId)};
  const arts = Array.from(document.querySelectorAll('article'));
  let art = null;
  if (tid) {
    for (const a of arts) {
      const has = Array.from(a.querySelectorAll('a[href*="/status/"]'))
        .some(x => (x.getAttribute('href') || '').includes('/status/' + tid));
      if (has) { art = a; break; }
    }
  }
  if (!art) art = arts.length ? arts[0] : null;
  if (!art) return JSON.stringify({ ok:false, err:'no-article' });
  let handle = '';
  const links = Array.from(art.querySelectorAll('a[href*="/status/"]'))
    .map(a => (a.getAttribute('href') || '').trim())
    .filter(h => h.includes('/status/'));
  for (const h of links) {
    const m = tid
      ? h.match(new RegExp('^/([^/]+)/status/' + tid))
      : h.match(/^\\/([^/]+)\\/status\\//);
    if (m && m[1] && m[1] !== 'i') { handle = m[1]; break; }
  }
  const timeEl = art.querySelector('time');
  const dt = timeEl ? (timeEl.getAttribute('datetime') || '') : '';
  const textNodes = Array.from(art.querySelectorAll('div[data-testid="tweetText"], div[lang]'));
  const parts = [];
  for (const n of textNodes) {
    const t = (n.innerText || '').trim();
    if (t && parts.indexOf(t) < 0) parts.push(t);
  }
  const imgs = Array.from(art.querySelectorAll('img'))
    .map(i => (i.getAttribute('src') || '').trim())
    .filter(s => s.includes('pbs.twimg.com/media/') || s.includes('pbs.twimg.com/tweet_video_thumb/') || s.includes('pbs.twimg.com/ext_tw_video_thumb/'));
  return JSON.stringify({ ok:true, dt, handle, text: parts.join('\\n'), imgs });
})()
""";
      final raw = await c.evaluateJavascript(source: js);
      final m = jsonDecode(raw.toString());
      if (m is Map && (m["ok"] == true)) {
        final dt = (m["dt"] ?? "").toString();
        final handle = (m["handle"] ?? "").toString();
        final text = (m["text"] ?? "").toString();
        final imgs = (m["imgs"] is List) ? (m["imgs"] as List) : const [];
        setState(() {
          if (dt.isNotEmpty) _dtUtc = dt;
          if ((_handle.isEmpty || _handle == "i") && handle.isNotEmpty) _handle = handle;
          if (text.isNotEmpty) _text = text;
          for (final u in imgs) {
            _imageUrls.add(_pbsToOrig(u.toString()));
          }
        });
        _pushLog("[extract] dt=${_dtUtc.isEmpty ? '(none)' : _dtUtc} text=${_text.length} imgs=${imgs.length}");
      } else {
        _pushLog("[extract] failed: ${m["err"] ?? "unknown"}");
      }

      final js2 = """
(() => {
  const perf = (performance.getEntriesByType('resource') || [])
    .map(e => (e && e.name) ? String(e.name) : '')
    .filter(s => s && s.length > 0);
  const hits = [];
  const html = document.documentElement ? document.documentElement.outerHTML : '';
  const rx = /(https?:)?\\/\\/(?:pbs\\.twimg\\.com\\/(?:media|tweet_video_thumb|ext_tw_video_thumb)\\/[^"'<\\s]+|video\\.twimg\\.com\\/[^"'<\\s]+)/g;
  let m;
  while ((m = rx.exec(html)) !== null) {
    let u = m[0] || '';
    if (u.startsWith('//')) u = 'https:' + u;
    hits.push(u);
    if (hits.length >= 200) break;
  }
  return JSON.stringify({ perf: perf.slice(0, 600), hits });
})()
""";
      final raw2 = await c.evaluateJavascript(source: js2);
      final m2 = jsonDecode(raw2.toString());
      if (m2 is Map) {
        final perf = (m2["perf"] is List) ? (m2["perf"] as List) : const [];
        final hits = (m2["hits"] is List) ? (m2["hits"] as List) : const [];
        var added = 0;
        for (final u in [...perf, ...hits]) {
          final s = u.toString();
          final beforeImg = _imageUrls.length;
          final beforeVid = _videoUrls.length;
          _observeUrl(s);
          if (_imageUrls.length != beforeImg || _videoUrls.length != beforeVid) {
            added += 1;
          }
          if (added >= 30) break;
        }
        _pushLog("[scan] perf=${perf.length} hits=${hits.length} added=$added");
      }
    } catch (e) {
      _pushLog("[extract] error: $e");
    }
  }

  Future<Map<String, String>> _headersWithCookies() async {
    final headers = <String, String>{
      "User-Agent":
          "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36",
      "Referer": "https://x.com/",
    };
    try {
      final cm = CookieManager.instance();
      final cookies = await cm.getCookies(url: WebUri("https://x.com/"));
      if (cookies.isNotEmpty) {
        headers["Cookie"] = cookies.map((c) => "${c.name}=${c.value}").join("; ");
      }
    } catch (_) {}
    return headers;
  }

  Future<void> _saveAll() async {
    if (_busy) return;
    if (_tweetId.isEmpty || _handle.isEmpty) {
      _pushLog("[save] URL 解析失败");
      return;
    }
    if (_text.trim().isEmpty && _imageUrls.isEmpty && _videoUrls.isEmpty) {
      _pushLog("[save] 未抓到内容：先点“刷新提取”，必要时在网页里登录/播放视频");
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("未抓到内容：先刷新提取/登录/播放视频")),
      );
      return;
    }
    setState(() => _busy = true);
    try {
      final base = Directory(widget.baseDir);
      final dtp = _parseIso(_dtUtc) ?? DateTime.now().toUtc();
      final yyyy = dtp.toUtc().year.toString().padLeft(4, "0");
      final ym = "${dtp.toUtc().year.toString().padLeft(4, "0")}-${dtp.toUtc().month.toString().padLeft(2, "0")}";
      final stamp =
          "${dtp.toUtc().year.toString().padLeft(4, "0")}${dtp.toUtc().month.toString().padLeft(2, "0")}${dtp.toUtc().day.toString().padLeft(2, "0")}T${dtp.toUtc().hour.toString().padLeft(2, "0")}${dtp.toUtc().minute.toString().padLeft(2, "0")}${dtp.toUtc().second.toString().padLeft(2, "0")}Z";
      final tweetDir = Directory(p.join(
        base.path,
        "x_media_ci",
        "accounts",
        _handle,
        "tweets",
        yyyy,
        ym,
        "${stamp}_$_tweetId",
      ));
      final imagesDir = Directory(p.join(tweetDir.path, "media", "images"));
      final videoDir = Directory(p.join(tweetDir.path, "media", "video"));
      final rawDir = Directory(p.join(tweetDir.path, "media", "raw"));
      final exportsDir = Directory(p.join(tweetDir.path, "exports"));
      await imagesDir.create(recursive: true);
      await videoDir.create(recursive: true);
      await rawDir.create(recursive: true);
      await exportsDir.create(recursive: true);

      _pushLog("[save] dir=${tweetDir.path}");

      final headers = await _headersWithCookies();
      final media = <Map<String, dynamic>>[];

      var imgIdx = 1;
      final imgList = _imageUrls.toList()..sort();
      for (final u in imgList) {
        final mid = _mediaIdFromUrl(u) ?? "img$imgIdx";
        final ext = _imgExt(u);
        final fname = "${imgIdx.toString().padLeft(2, "0")}_$mid$ext";
        final out = File(p.join(imagesDir.path, fname));
        try {
          await _downloadToFile(u, out, headers: headers);
          media.add({
            "type": "image",
            "mime": "image/${ext.replaceFirst('.', '')}",
            "file": fname,
            "source_url": u,
          });
          _pushLog("[img] ok $fname (${out.lengthSync()})");
          imgIdx += 1;
        } catch (e) {
          await File(p.join(rawDir.path, "image_${imgIdx.toString().padLeft(2, "0")}_error.txt"))
              .writeAsString(e.toString());
          _pushLog("[img] fail $e");
          imgIdx += 1;
        }
      }

      final videosJson = <String, dynamic>{};
      final keys = _videoUrls.keys.toList()..sort();
      for (final k in keys) {
        final g = _videoUrls[k]!;
        videosJson[k] = {
          "mp4": g["mp4"]!.toList()..sort(),
          "m3u8": g["m3u8"]!.toList()..sort(),
        };
      }
      await File(p.join(rawDir.path, "video_urls.json"))
          .writeAsString(const JsonEncoder.withIndent("  ").convert(videosJson));

      int areaOf(String u) {
        final m = RegExp(r"/vid/(?:[a-zA-Z0-9_-]+/)?(\d+)x(\d+)/").firstMatch(u);
        final w = int.tryParse(m?.group(1) ?? "") ?? 0;
        final h = int.tryParse(m?.group(2) ?? "") ?? 0;
        return w * h;
      }

      final groups = <String, ({int bestArea, List<String> mp4, List<String> m3u8})>{};
      var anyM3u8 = false;
      for (final k in keys) {
        final g = _videoUrls[k]!;
        final mp4Urls = g["mp4"]!
            .where((u) => u.contains(".mp4"))
            .where((u) => u.contains("/vid/") && !u.contains("/aud/"))
            .toList();
        final m3u8Urls = g["m3u8"]!.toList();
        if (m3u8Urls.isNotEmpty) anyM3u8 = true;
        var bestArea = 0;
        for (final u in mp4Urls) {
          final a = areaOf(u);
          if (a > bestArea) bestArea = a;
        }
        groups[k] = (bestArea: bestArea, mp4: mp4Urls, m3u8: m3u8Urls);
      }

      final pickedKeys = keys.toList()
        ..sort((a, b) => (groups[b]?.bestArea ?? 0).compareTo(groups[a]?.bestArea ?? 0));
      final chosenKeys = pickedKeys.take(3).toList();

      if (chosenKeys.isEmpty) {
        _pushLog("[vid] no mp4 captured. Press 刷新提取, then tap Play once and Save again.");
        if (anyM3u8) {
          _pushLog("[vid] m3u8 captured; if mp4 is missing, the tweet may be streaming-only.");
        }
      } else {
        var vIdx = 1;
        for (final k in chosenKeys) {
          final g = groups[k]!;
          final mp4s = g.mp4.toList()..sort((a, b) => areaOf(b).compareTo(areaOf(a)));
          final vname = "${_tweetId}_video_${vIdx.toString().padLeft(2, "0")}.mp4";
          final out = File(p.join(videoDir.path, vname));

          var ok = false;
          for (final u in mp4s) {
            final clen = await _probeContentLength(u, headers: headers);
            if (clen > 0 && clen < 200 * 1024) {
              _pushLog("[vid] skip tiny mp4 content-length=$clen url=$u");
              continue;
            }
            try {
              await _downloadToFile(u, out, headers: headers, validateMp4: true);
              media.add({
                "type": "video",
                "mime": "video/mp4",
                "file": vname,
                "source_url": u,
              });
              _pushLog("[vid] ok mp4 $vname (${out.lengthSync()}) area=${areaOf(u)} group=$k");
              ok = true;
              break;
            } catch (e) {
              _pushLog("[vid] mp4 fail $e");
            }
          }

          if (!ok && g.m3u8.isNotEmpty) {
            try {
              final m3u8 = await _pickBestM3u8(g.m3u8, headers: headers) ?? g.m3u8.first;
              await File(p.join(rawDir.path, "video_m3u8_chosen_${vIdx.toString().padLeft(2, "0")}.txt"))
                  .writeAsString(m3u8);
              final hlsOk = await _downloadHlsToFile(m3u8, out, headers: headers);
              if (hlsOk && out.existsSync() && out.lengthSync() > 200 * 1024) {
                media.add({
                  "type": "video",
                  "mime": "video/mp4",
                  "file": vname,
                  "source_url": m3u8,
                  "derived_from": "m3u8",
                });
                _pushLog("[vid] ok hls $vname (${out.lengthSync()}) group=$k");
                ok = true;
              } else {
                try {
                  if (out.existsSync()) await out.delete();
                } catch (_) {}
                _pushLog("[vid] hls failed (may need ffmpeg remux)");
              }
            } catch (e) {
              _pushLog("[vid] hls fail $e");
            }
          }

          if (!ok) {
            await File(p.join(rawDir.path, "video_error_${vIdx.toString().padLeft(2, "0")}.txt"))
                .writeAsString("group=$k\nmp4=${g.mp4.length}\nm3u8=${g.m3u8.length}\n");
            _pushLog("[vid] failed to save group=$k");
          }
          vIdx += 1;
        }
      }

      final meta = <String, dynamic>{
        "source": "x.com",
        "ci_version": "1.0",
        "tweet_id": _tweetId,
        "tweet_url": _url,
        "author_handle": _handle,
        "datetime_utc": _dtUtc.isEmpty ? dtp.toUtc().toIso8601String() : _dtUtc,
        "datetime_beijing": _toBeijingIso(dtp),
        "fetched_at": DateTime.now().toUtc().toIso8601String().split("T").first,
        "text": _text,
        "media": media,
        "exports": [],
        "note": "fetched on Android (WebView capture).",
      };
      await File(p.join(tweetDir.path, "tweet.json"))
          .writeAsString(const JsonEncoder.withIndent("  ").convert(meta));

      final extract = _buildExtract(meta);
      final extractPath = p.join(exportsDir.path, "article_${p.basename(tweetDir.path)}_extract.json");
      await File(extractPath).writeAsString(const JsonEncoder.withIndent("  ").convert(extract));

      final mdPath = p.join(exportsDir.path, "article_${p.basename(tweetDir.path)}_full.md");
      await File(mdPath).writeAsString(_renderMarkdown(extract));

      final pdfPath = p.join(exportsDir.path, "article_${p.basename(tweetDir.path)}_full.pdf");
      await _writePdf(
        pdfPath,
        title: (extract["title"] ?? "X Article").toString(),
        url: (extract["url"] ?? "").toString(),
        author: (extract["author_handle"] ?? "").toString(),
        dtUtc: (extract["datetime_utc"] ?? "").toString(),
        text: _text,
        images: imagesDir,
      );

      _pushLog("[done] md/pdf ok");
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("完成：${tweetDir.path}")),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

(String, String) _parseTweetUrl(String url) {
  final re = RegExp(r"^https?://(x\.com|twitter\.com)/([^/]+)/status/(\d+)");
  final m = re.firstMatch(url.trim());
  if (m == null) return ("", "");
  return (m.group(2) ?? "", m.group(3) ?? "");
}

DateTime? _parseIso(String s) {
  if (s.trim().isEmpty) return null;
  try {
    return DateTime.parse(s).toUtc();
  } catch (_) {
    return null;
  }
}

String _toBeijingIso(DateTime dtUtc) {
  final bj = dtUtc.toUtc().add(const Duration(hours: 8));
  final y = bj.year.toString().padLeft(4, "0");
  final m = bj.month.toString().padLeft(2, "0");
  final d = bj.day.toString().padLeft(2, "0");
  final hh = bj.hour.toString().padLeft(2, "0");
  final mm = bj.minute.toString().padLeft(2, "0");
  final ss = bj.second.toString().padLeft(2, "0");
  return "$y-$m-$d" "T$hh:$mm:$ss+08:00";
}

String _pbsToOrig(String url) {
  try {
    final u = Uri.parse(url);
    if (!u.host.contains("pbs.twimg.com")) return url;
    final q = Map<String, String>.from(u.queryParameters);
    q["name"] = "orig";
    return u.replace(queryParameters: q).toString();
  } catch (_) {
    return url;
  }
}

String? _mediaIdFromUrl(String url) {
  final m = RegExp(r"/media/([^?]+)").firstMatch(url);
  if (m == null) return null;
  final raw = m.group(1) ?? "";
  final base = raw.split("/").last;
  final stem = base.split(".").first;
  return stem.replaceAll(RegExp(r"[^a-zA-Z0-9_-]+"), "_");
}

String _imgExt(String url) {
  try {
    final u = Uri.parse(url);
    final fmt = u.queryParameters["format"];
    if (fmt != null && fmt.isNotEmpty) return ".${fmt.toLowerCase()}";
    final pathExt = p.extension(u.path);
    if (pathExt.isNotEmpty) return pathExt.toLowerCase();
  } catch (_) {}
  return ".jpg";
}

String _videoGroupKey(String url) {
  for (final pat in [
    RegExp(r"/amplify_video/(\d+)/"),
    RegExp(r"/ext_tw_video/(\d+)/"),
    RegExp(r"/tweet_video/(\d+)/"),
  ]) {
    final m = pat.firstMatch(url);
    if (m != null) return m.group(1) ?? url;
  }
  return url.split("?").first;
}

String? _pickBestMp4(List<String> urls) {
  String? best;
  var bestArea = -1;
  for (final u in urls) {
    final m = RegExp(r"/vid/(\d+)x(\d+)/").firstMatch(u);
    var area = 0;
    if (m != null) {
      area = int.tryParse(m.group(1) ?? "0")! * int.tryParse(m.group(2) ?? "0")!;
    }
    if (area > bestArea) {
      bestArea = area;
      best = u;
    }
  }
  return best ?? (urls.isNotEmpty ? urls.first : null);
}

bool _looksLikeMp4(List<int> bytes) {
  if (bytes.length < 12) return false;
  final s = String.fromCharCodes(bytes.take(64));
  if (s.startsWith("<!DOCTYPE") || s.startsWith("<html") || s.startsWith("<?xml")) return false;
  if (bytes.length >= 8) {
    final tag = String.fromCharCodes(bytes.sublist(4, 8));
    if (tag == "ftyp") return true;
  }
  return false;
}

String _snippetText(List<int> bytes) {
  final n = bytes.length > 96 ? 96 : bytes.length;
  final b = bytes.sublist(0, n);
  final hex = b.map((x) => x.toRadixString(16).padLeft(2, "0")).join();
  var ascii = "";
  for (final x in b) {
    if (x >= 0x20 && x <= 0x7E) {
      ascii += String.fromCharCode(x);
    } else {
      ascii += ".";
    }
  }
  return "hex=$hex ascii=$ascii";
}

Future<void> _downloadToFile(
  String url,
  File out, {
  required Map<String, String> headers,
  bool validateMp4 = false,
}) async {
  final client = http.Client();
  try {
    final req = http.Request("GET", Uri.parse(url));
    req.headers.addAll(headers);
    if (validateMp4) {
      req.headers["Accept"] = "*/*";
    }
    final resp = await client.send(req);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw Exception("HTTP ${resp.statusCode} for $url");
    }
    final ct = (resp.headers["content-type"] ?? "").toLowerCase();
    if (validateMp4 && (ct.contains("text/html") || ct.contains("application/json"))) {
      throw Exception("Not mp4 (content-type=$ct)");
    }
    await out.parent.create(recursive: true);
    final sink = out.openWrite();
    final head = <int>[];
    var total = 0;
    try {
      await for (final chunk in resp.stream) {
        total += chunk.length;
        if (head.length < 96) {
          final need = 96 - head.length;
          head.addAll(chunk.take(need));
        }
        sink.add(chunk);
      }
    } finally {
      await sink.close();
    }
    if (validateMp4) {
      if (total < 200 * 1024) {
        try {
          await out.delete();
        } catch (_) {}
        throw Exception("MP4 too small ($total bytes) head=${_snippetText(head)} ct=$ct");
      }
      if (!_looksLikeMp4(head)) {
        try {
          await out.delete();
        } catch (_) {}
        throw Exception("Not mp4 head=${_snippetText(head)} ct=$ct");
      }
    }
  } finally {
    client.close();
  }
}

Future<int> _probeContentLength(String url, {required Map<String, String> headers}) async {
  final client = http.Client();
  try {
    final req = http.Request("HEAD", Uri.parse(url));
    req.headers.addAll(headers);
    final resp = await client.send(req);
    if (resp.statusCode >= 200 && resp.statusCode < 400) {
      final v = resp.headers["content-length"];
      final n = int.tryParse(v ?? "");
      if (n != null) return n;
      return 0;
    }
    if (resp.statusCode == 405 || resp.statusCode == 403) {
      final r = http.Request("GET", Uri.parse(url));
      r.headers.addAll(headers);
      r.headers["Range"] = "bytes=0-0";
      final rr = await client.send(r);
      if (rr.statusCode >= 200 && rr.statusCode < 400) {
        final v = rr.headers["content-range"] ?? rr.headers["content-length"] ?? "";
        final m = RegExp(r"/(\d+)$").firstMatch(v);
        if (m != null) return int.tryParse(m.group(1) ?? "") ?? 0;
        return int.tryParse(rr.headers["content-length"] ?? "") ?? 0;
      }
    }
    return 0;
  } catch (_) {
    return 0;
  } finally {
    client.close();
  }
}

Future<String?> _pickBestM3u8(List<String> urls, {required Map<String, String> headers}) async {
  (int, int, String)? best;
  for (final u in urls) {
    String txt;
    try {
      final resp = await http.get(Uri.parse(u), headers: headers);
      if (resp.statusCode >= 400) continue;
      txt = utf8.decode(resp.bodyBytes, allowMalformed: true);
    } catch (_) {
      continue;
    }
    if (!txt.contains("#EXTM3U")) continue;
    if (txt.contains("#EXT-X-STREAM-INF")) {
      final lines = txt.split("\n").map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
      for (var i = 0; i < lines.length; i++) {
        final ln = lines[i];
        if (!ln.startsWith("#EXT-X-STREAM-INF:")) continue;
        final attrs = ln.substring("#EXT-X-STREAM-INF:".length);
        final bw = int.tryParse(RegExp(r"BANDWIDTH=(\d+)").firstMatch(attrs)?.group(1) ?? "") ?? 0;
        final resM = RegExp(r"RESOLUTION=(\d+)x(\d+)").firstMatch(attrs);
        final area = resM == null
            ? 0
            : (int.tryParse(resM.group(1) ?? "0") ?? 0) * (int.tryParse(resM.group(2) ?? "0") ?? 0);
        var j = i + 1;
        while (j < lines.length && lines[j].startsWith("#")) {
          j += 1;
        }
        if (j >= lines.length) continue;
        final variant = Uri.parse(u).resolve(lines[j]).toString();
        final cand = (area, bw, variant);
        if (best == null || cand.$1 > best.$1 || (cand.$1 == best.$1 && cand.$2 > best.$2)) {
          best = cand;
        }
      }
    } else {
      final cand = (0, 0, u);
      if (best == null) best = cand;
    }
  }
  return best?.$3;
}

Future<bool> _downloadHlsToFile(String m3u8Url, File out, {required Map<String, String> headers}) async {
  final resp = await http.get(Uri.parse(m3u8Url), headers: headers);
  if (resp.statusCode >= 400) return false;
  final txt = utf8.decode(resp.bodyBytes, allowMalformed: true);
  if (!txt.contains("#EXTM3U")) return false;
  final lines = txt.split("\n").map((e) => e.trim()).toList();
  String? mapUrl;
  final mapM = RegExp(r'#EXT-X-MAP:URI="([^"]+)"').firstMatch(txt);
  if (mapM != null) {
    mapUrl = Uri.parse(m3u8Url).resolve(mapM.group(1)!).toString();
  }
  final segs = <String>[];
  for (final ln in lines) {
    if (ln.isEmpty || ln.startsWith("#")) continue;
    segs.add(Uri.parse(m3u8Url).resolve(ln).toString());
  }
  if (segs.isEmpty) return false;
  await out.parent.create(recursive: true);
  final sink = out.openWrite();
  try {
    if (mapUrl != null) {
      final r0 = await http.get(Uri.parse(mapUrl), headers: headers);
      if (r0.statusCode >= 400) return false;
      sink.add(r0.bodyBytes);
    }
    for (final s in segs) {
      final r = await http.get(Uri.parse(s), headers: headers);
      if (r.statusCode >= 400) return false;
      sink.add(r.bodyBytes);
    }
  } finally {
    await sink.close();
  }
  return out.lengthSync() > 200 * 1024;
}

Map<String, dynamic> _buildExtract(Map<String, dynamic> meta) {
  final text = (meta["text"] ?? "").toString();
  final nodes = <Map<String, dynamic>>[];
  if (text.isNotEmpty) {
    for (final para in text.split("\n\n")) {
      final t = para.trim();
      if (t.isNotEmpty) nodes.add({"type": "p", "text": t});
    }
  }
  final media = (meta["media"] is List) ? (meta["media"] as List) : const [];
  for (final m in media) {
    if (m is Map && m["type"] == "image" && m["source_url"] != null) {
      nodes.add({"type": "img", "src": m["source_url"].toString()});
    }
  }
  return {
    "title": (text.isNotEmpty ? text.split("\n").first : "Tweet ${meta["tweet_id"] ?? ""}"),
    "url": meta["tweet_url"] ?? "",
    "author_handle": meta["author_handle"] ?? "",
    "datetime_utc": meta["datetime_utc"] ?? "",
    "nodes": nodes,
  };
}

String _renderMarkdown(Map<String, dynamic> extract) {
  final title = (extract["title"] ?? "X Article").toString();
  final url = (extract["url"] ?? "").toString();
  final author = (extract["author_handle"] ?? "").toString();
  final dt = (extract["datetime_utc"] ?? "").toString();
  final buf = StringBuffer();
  buf.writeln("# $title");
  buf.writeln();
  buf.writeln("- 作者：$author");
  buf.writeln("- 文章链接：$url");
  buf.writeln("- 时间（UTC）：$dt");
  buf.writeln();
  buf.writeln("---");
  buf.writeln();
  final nodes = (extract["nodes"] is List) ? (extract["nodes"] as List) : const [];
  for (final n in nodes) {
    if (n is! Map) continue;
    final t = (n["type"] ?? "").toString();
    if (t == "p") {
      final s = (n["text"] ?? "").toString().trim();
      if (s.isNotEmpty) {
        buf.writeln(s);
        buf.writeln();
      }
    } else if (t == "img") {
      final src = (n["src"] ?? "").toString();
      if (src.isNotEmpty) {
        buf.writeln("![]($src)");
        buf.writeln();
      }
    }
  }
  return buf.toString();
}

Future<void> _writePdf(
  String outPath, {
  required String title,
  required String url,
  required String author,
  required String dtUtc,
  required String text,
  required Directory images,
}) async {
  final doc = pw.Document();
  final imgs = images
      .listSync()
      .whereType<File>()
      .where((f) => f.path.toLowerCase().endsWith(".jpg") || f.path.toLowerCase().endsWith(".png") || f.path.toLowerCase().endsWith(".jpeg"))
      .toList()
    ..sort((a, b) => a.path.compareTo(b.path));
  doc.addPage(
    pw.MultiPage(
      build: (ctx) {
        final out = <pw.Widget>[];
        out.add(pw.Text(title, style: pw.TextStyle(fontSize: 20, fontWeight: pw.FontWeight.bold)));
        out.add(pw.SizedBox(height: 8));
        out.add(pw.Text("作者：$author"));
        out.add(pw.Text("链接：$url"));
        out.add(pw.Text("时间（UTC）：$dtUtc"));
        out.add(pw.SizedBox(height: 12));
        if (text.trim().isNotEmpty) {
          out.add(pw.Text(text));
          out.add(pw.SizedBox(height: 12));
        }
        for (final f in imgs) {
          try {
            final bytes = f.readAsBytesSync();
            final img = pw.MemoryImage(bytes);
            out.add(pw.Center(child: pw.Image(img, height: 520, fit: pw.BoxFit.contain)));
            out.add(pw.SizedBox(height: 10));
          } catch (_) {}
        }
        return out;
      },
    ),
  );
  final file = File(outPath);
  await file.parent.create(recursive: true);
  await file.writeAsBytes(await doc.save());
}
