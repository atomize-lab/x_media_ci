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
  String? _health;

  @override
  void initState() {
    super.initState();
    _ctrl = TextEditingController(text: CiApi.instance.baseUrl);
  }

  @override
  void dispose() {
    _ctrl.dispose();
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
        TextField(
          controller: _ctrl,
          decoration: const InputDecoration(
            labelText: "Server base URL",
            hintText: "http://<PC_IP>:8765",
          ),
        ),
        const SizedBox(height: 12),
        Row(children: [
          FilledButton(
            onPressed: () {
              CiApi.instance.baseUrl = _ctrl.text;
              CiApi.instance.save();
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("Saved")),
              );
            },
            child: const Text("Save"),
          ),
          const SizedBox(width: 12),
          OutlinedButton(
            onPressed: _ping,
            child: const Text("Ping /api/health"),
          ),
        ]),
        const SizedBox(height: 12),
        if (_health != null) Text(_health!),
      ],
    );
  }
}
