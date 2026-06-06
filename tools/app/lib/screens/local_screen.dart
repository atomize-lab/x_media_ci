// Local screen: independent download on the phone.
//
// This is a deliberately minimal scaffold. Production implementation
// should use `dio` for resumable downloads and `path_provider` for
// the app's documents directory. We intentionally keep this UI-only
// for now so the rest of the app is exercisable.
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

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
      final d = await getApplicationDocumentsDirectory();
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
        const Text(
          "Paste a tweet URL to download media into the app's local "
          "sandbox. (Implementation TODO: plug in dio + a tweet fetcher "
          "that produces a CI-shaped folder on the device.)",
        ),
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
          label: const Text("Download (TODO)"),
          onPressed: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text("Downloader not wired yet")),
            );
          },
        ),
      ],
    );
  }
}
