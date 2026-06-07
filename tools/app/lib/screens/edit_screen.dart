// Edit screen: pull a tweet.json from the server, let the user tweak it,
// and PUT it back. This is the "manual annotation" path.
//
// For richer editing (lists, structured fields) we will eventually
// generate a form. For the initial version we expose a multi-line
// JSON editor with parse-on-save validation.
import 'dart:convert';

import 'package:flutter/material.dart';

import '../api/ci_api.dart';
import 'settings_screen.dart';

class EditScreen extends StatefulWidget {
  const EditScreen({super.key});

  @override
  State<EditScreen> createState() => _EditScreenState();
}

class _EditScreenState extends State<EditScreen> {
  final _tweetId = TextEditingController();
  final _body = TextEditingController();
  bool _busy = false;
  String? _error;

  Future<void> _load() async {
    if (_tweetId.text.trim().isEmpty) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final d = await CiApi.instance.tweet(_tweetId.text.trim());
      final pretty = const JsonEncoder.withIndent("  ").convert(d.meta);
      if (!mounted) return;
      setState(() {
        _body.text = pretty;
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = "$e";
        _busy = false;
      });
    }
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final dynamic parsed = jsonDecode(_body.text);
      if (parsed is! Map) {
        throw const FormatException("tweet.json must be a JSON object");
      }
      await CiApi.instance.updateTweet(
        _tweetId.text.trim(),
        parsed.cast<String, dynamic>(),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Saved")),
      );
      setState(() => _busy = false);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = "$e";
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!CiApi.instance.remoteEnabled) {
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const SizedBox(height: 120),
          const Icon(Icons.cloud_off, size: 48),
          const SizedBox(height: 12),
          const Center(child: Text("Edit 默认关闭（不依赖电脑）")),
          const SizedBox(height: 8),
          Center(
            child: Text(
              "要编辑电脑端 tweet.json，请去 Settings 开启并配置。",
              style: const TextStyle(fontFamily: "monospace", fontSize: 12),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
            child: const Text("去开启电脑服务"),
          ),
        ],
      );
    }
    if (!CiApi.instance.isConfigured) {
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const SizedBox(height: 120),
          const Icon(Icons.settings_ethernet, size: 48),
          const SizedBox(height: 12),
          const Center(child: Text("未设置 Server URL")),
          const SizedBox(height: 8),
          const Center(
            child: Text(
              "去 Settings 填 http://<PC_IP>:8765",
              style: TextStyle(fontFamily: "monospace", fontSize: 12),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
            child: const Text("去设置"),
          ),
        ],
      );
    }
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _tweetId,
                  decoration: const InputDecoration(
                    labelText: "Tweet ID (numeric)",
                  ),
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: _busy ? null : _load,
                child: const Text("Load"),
              ),
            ],
          ),
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Text(_error!, style: const TextStyle(color: Colors.red)),
          ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _body,
              maxLines: null,
              expands: true,
              textAlignVertical: TextAlignVertical.top,
              style: const TextStyle(fontFamily: "monospace", fontSize: 12),
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                hintText: "// tweet.json will appear here after Load",
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: FilledButton.icon(
            icon: const Icon(Icons.save),
            label: const Text("Save"),
            onPressed: _busy ? null : _save,
          ),
        ),
      ],
    );
  }
}
