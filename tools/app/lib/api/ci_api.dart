// Centralized HTTP client + typed models for the x_media CI server.
//
// All UI code talks to the server through this class so that:
///  * the base URL is configurable (settings screen),
///  * auth tokens / timeouts are uniform,
///  * error handling is consistent.
import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class CiApi {
  CiApi._();
  static final CiApi instance = CiApi._();

  static const _kBaseUrlKey = "ci.base_url";
  String _baseUrl = "http://10.0.2.2:8765"; // android emulator -> host

  String get baseUrl => _baseUrl;
  set baseUrl(String v) {
    _baseUrl = v.trim().replaceAll(RegExp(r'/+$'), '');
  }

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    final v = p.getString(_kBaseUrlKey);
    if (v != null && v.isNotEmpty) _baseUrl = v;
  }

  Future<void> save() async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kBaseUrlKey, _baseUrl);
  }

  Uri _u(String path) => Uri.parse("$_baseUrl$path");

  // ----- low-level helpers ---------------------------------------------------

  Future<dynamic> _get(String path) async {
    final r = await http.get(_u(path)).timeout(const Duration(seconds: 15));
    return _decode(r);
  }

  Future<dynamic> _post(String path, Map<String, dynamic> body) async {
    final r = await http
        .post(_u(path),
            headers: const {"Content-Type": "application/json"},
            body: jsonEncode(body))
        .timeout(const Duration(minutes: 5));
    return _decode(r);
  }

  Future<dynamic> _put(String path, Map<String, dynamic> body) async {
    final r = await http
        .put(_u(path),
            headers: const {"Content-Type": "application/json"},
            body: jsonEncode(body))
        .timeout(const Duration(seconds: 30));
    return _decode(r);
  }

  dynamic _decode(http.Response r) {
    if (r.statusCode >= 200 && r.statusCode < 300) {
      if (r.body.isEmpty) return null;
      return jsonDecode(r.body);
    }
    throw HttpException(r.statusCode, r.body);
  }

  // ----- typed endpoints -----------------------------------------------------

  Future<Health> health() async {
    final j = await _get("/api/health") as Map<String, dynamic>;
    return Health.fromJson(j);
  }

  Future<List<Account>> accounts() async {
    final j = await _get("/api/accounts") as Map<String, dynamic>;
    return (j["accounts"] as List)
        .map((e) => Account.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<AccountDetail> accountDetail(String handle) async {
    final j = await _get("/api/accounts/$handle") as Map<String, dynamic>;
    return AccountDetail.fromJson(j);
  }

  Future<TweetDetail> tweet(String tweetId) async {
    final j = await _get("/api/tweet/$tweetId") as Map<String, dynamic>;
    return TweetDetail.fromJson(j);
  }

  Future<void> updateTweet(String tweetId, Map<String, dynamic> meta) async {
    await _put("/api/tweet/$tweetId", {"meta": meta});
  }

  Future<String> runOp(String op, Map<String, dynamic> args) async {
    final j = await _post("/api/run", {"op": op, "args": args})
        as Map<String, dynamic>;
    return j["job_id"] as String;
  }

  Future<Job> job(String id) async {
    final j = await _get("/api/jobs/$id") as Map<String, dynamic>;
    return Job.fromJson(j);
  }
}

class HttpException implements Exception {
  final int status;
  final String body;
  HttpException(this.status, this.body);
  @override
  String toString() => "HTTP $status: ${body.isEmpty ? '<empty>' : body}";
}

// ---------------------------------------------------------------------------
// Models (kept tiny on purpose; expand as UI needs grow)
// ---------------------------------------------------------------------------

class Health {
  final bool ok;
  final String ciRoot;
  final String ciRootExists;
  Health({required this.ok, required this.ciRoot, required this.ciRootExists});
  factory Health.fromJson(Map<String, dynamic> j) => Health(
        ok: j["ok"] == true,
        ciRoot: (j["ci_root"] ?? "").toString(),
        ciRootExists: (j["ci_root_exists"] ?? false).toString(),
      );
  String get ciRootExistsText =>
      ciRootExists == "true" ? "exists" : "missing";
}

class Account {
  final String handle;
  final int tweetCount;
  Account({required this.handle, required this.tweetCount});
  factory Account.fromJson(Map<String, dynamic> j) => Account(
        handle: j["handle"] as String,
        tweetCount: (j["tweet_count"] as num).toInt(),
      );
}

class MonthBucket {
  final String key; // "YYYY/YYYY-MM"
  final int count;
  MonthBucket({required this.key, required this.count});
  factory MonthBucket.fromJson(Map<String, dynamic> j) => MonthBucket(
        key: j["key"] as String,
        count: (j["count"] as num).toInt(),
      );
}

class AccountDetail {
  final String handle;
  final int tweetCount;
  final List<MonthBucket> months;
  AccountDetail({
    required this.handle,
    required this.tweetCount,
    required this.months,
  });
  factory AccountDetail.fromJson(Map<String, dynamic> j) => AccountDetail(
        handle: j["handle"] as String,
        tweetCount: (j["tweet_count"] as num).toInt(),
        months: ((j["months"] as List?) ?? const [])
            .map((e) => MonthBucket.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class MediaItem {
  final String sub;
  final String name;
  final int size;
  final String url;
  MediaItem({
    required this.sub,
    required this.name,
    required this.size,
    required this.url,
  });
  factory MediaItem.fromJson(Map<String, dynamic> j) => MediaItem(
        sub: j["sub"] as String,
        name: j["name"] as String,
        size: (j["size"] as num).toInt(),
        url: j["url"] as String,
      );
}

class TweetDetail {
  final String tweetId;
  final String handle;
  final String dir;
  final Map<String, dynamic> meta;
  final List<MediaItem> media;
  TweetDetail({
    required this.tweetId,
    required this.handle,
    required this.dir,
    required this.meta,
    required this.media,
  });
  factory TweetDetail.fromJson(Map<String, dynamic> j) => TweetDetail(
        tweetId: j["tweet_id"] as String,
        handle: (j["handle"] ?? "") as String,
        dir: (j["dir"] ?? "") as String,
        meta: (j["meta"] as Map?)?.cast<String, dynamic>() ?? const {},
        media: ((j["media"] as List?) ?? const [])
            .map((e) => MediaItem.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class Job {
  final String id;
  final String op;
  final String status;
  final int? returncode;
  Job({required this.id, required this.op, required this.status, this.returncode});
  factory Job.fromJson(Map<String, dynamic> j) => Job(
        id: j["id"] as String,
        op: j["op"] as String,
        status: j["status"] as String,
        returncode: (j["returncode"] as num?)?.toInt(),
      );
  bool get isDone => status == "done" || status == "failed";
}

@visibleForTesting
String apiBaseUrlForTests() => CiApi.instance.baseUrl;
