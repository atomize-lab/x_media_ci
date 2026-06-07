// Settings screen: configure the server base URL.
//
// On Android emulator the default `10.0.2.2` already maps to host's
// `127.0.0.1`. For real devices, set the PC's LAN IP (or use
// `adb reverse tcp:8765 tcp:8765` + `127.0.0.1`).
import 'package:flutter/material.dart';

import '../api/ci_api.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _ctrl;
  late final TextEditingController _authToken;
  late final TextEditingController _ct0;
  String? _health;
  bool _remoteEnabled = false;

  @override
  void initState() {
    super.initState();
    _ctrl = TextEditingController(text: CiApi.instance.baseUrl);
    _authToken = TextEditingController(text: CiApi.instance.xAuthToken);
    _ct0 = TextEditingController(text: CiApi.instance.xCt0);
    _remoteEnabled = CiApi.instance.remoteEnabled;
  }

  @override
  void dispose() {
    _ctrl.dispose();
    _authToken.dispose();
    _ct0.dispose();
    super.dispose();
  }

  Future<void> _ping() async {
    setState(() => _health = "checking...");
    try {
      final h = await CiApi.instance.health();
      setState(() => _health =
          "OK — ci_root=${h.ciRoot} (${h.ciRootExistsText})");
    } catch (e) {
      setState(() => _health = "FAIL: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text(
          "X 登录态（可选）：填 auth_token + ct0 后，Local 抓取会直接注入 Cookie，尽量避免网页登录。\n"
          "不要把这两个值发给任何人。",
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _authToken,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: "auth_token",
            hintText: "从浏览器 Cookie 复制 value",
          ),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _ct0,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: "ct0",
            hintText: "从浏览器 Cookie 复制 value",
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton(
              onPressed: () => setState(() {
                _authToken.text = "";
                _ct0.text = "";
              }),
              child: const Text("清空 X Cookie"),
            ),
          ],
        ),
        const Divider(height: 32),
        SwitchListTile(
          title: const Text("启用电脑服务（Browse/Remote/Edit）"),
          subtitle: const Text("关闭后 App 完全不依赖电脑，只用 Local。"),
          value: _remoteEnabled,
          onChanged: (v) => setState(() => _remoteEnabled = v),
        ),
        const Text(
          "真机要填电脑的局域网 IP，例如：http://192.168.1.23:8765\n"
          "模拟器才用：http://10.0.2.2:8765",
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _ctrl,
          decoration: const InputDecoration(
            labelText: "Server base URL",
            hintText: "http://<PC_IP>:8765",
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton(
              onPressed: () => setState(() => _ctrl.text = ""),
              child: const Text("清空"),
            ),
            OutlinedButton(
              onPressed: () => setState(() => _ctrl.text = "http://10.0.2.2:8765"),
              child: const Text("模拟器 10.0.2.2"),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(children: [
          FilledButton(
            onPressed: () {
              CiApi.instance.baseUrl = _ctrl.text;
              CiApi.instance.remoteEnabled = _remoteEnabled;
              CiApi.instance.xAuthToken = _authToken.text;
              CiApi.instance.xCt0 = _ct0.text;
              CiApi.instance.save();
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("Saved")),
              );
            },
            child: const Text("Save"),
          ),
          const SizedBox(width: 12),
          OutlinedButton(
            onPressed: _remoteEnabled ? _ping : null,
            child: const Text("Ping /api/health"),
          ),
        ]),
        const SizedBox(height: 12),
        if (_health != null) Text(_health!),
      ],
    );
  }
}
