// Remote screen: fire a job on the PC and watch its progress.
//
// Backend:  POST /api/run   -> {job_id}
//           GET  /api/jobs/{id} -> status / returncode / stderr tail
import 'dart:async';

import 'package:flutter/material.dart';

import '../api/ci_api.dart';

class RemoteScreen extends StatefulWidget {
  const RemoteScreen({super.key});

  @override
  State<RemoteScreen> createState() => _RemoteScreenState();
}

class _RemoteScreenState extends State<RemoteScreen> {
  final _tweetDir = TextEditingController();
  String _op = "all";
  bool _withOcr = false;
  bool _busy = false;
  String? _lastJobId;
  Job? _job;
  Timer? _poller;

  @override
  void dispose() {
    _tweetDir.dispose();
    _poller?.cancel();
    super.dispose();
  }

  Future<void> _run() async {
    if (_tweetDir.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("tweet_dir is required")),
      );
      return;
    }
    setState(() {
      _busy = true;
      _job = null;
    });
    try {
      final id = await CiApi.instance.runOp(_op, {
        "tweet_dir": _tweetDir.text.trim(),
        if (_op == "all" && _withOcr) "with_ocr": true,
        "force": true,
      });
      _lastJobId = id;
      _poller?.cancel();
      _poller = Timer.periodic(const Duration(seconds: 1), (t) async {
        try {
          final j = await CiApi.instance.job(id);
          if (!mounted) return;
          setState(() => _job = j);
          if (j.isDone) {
            t.cancel();
            setState(() => _busy = false);
          }
        } catch (e) {
          if (!mounted) return;
          setState(() => _busy = false);
          t.cancel();
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text("poll failed: $e")),
          );
        }
      });
    } catch (e) {
      setState(() => _busy = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("run failed: $e")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text("Server: ${CiApi.instance.baseUrl}",
            style: const TextStyle(fontFamily: "monospace")),
        const SizedBox(height: 16),
        DropdownButtonFormField<String>(
          value: _op,
          decoration: const InputDecoration(labelText: "Operation"),
          items: const [
            DropdownMenuItem(value: "md", child: Text("md — generate .md")),
            DropdownMenuItem(value: "pdf", child: Text("pdf — generate .pdf")),
            DropdownMenuItem(value: "ocr", child: Text("ocr — run OCR pipeline")),
            DropdownMenuItem(value: "all", child: Text("all — md + pdf (+ ocr)")),
            DropdownMenuItem(value: "fix", child: Text("fix — normalize tweet.json")),
            DropdownMenuItem(value: "transcode", child: Text("transcode — H.264/AAC")),
            DropdownMenuItem(value: "validate", child: Text("validate — schema check")),
          ],
          onChanged: (v) => setState(() => _op = v ?? "all"),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _tweetDir,
          decoration: const InputDecoration(
            labelText: "tweet_dir (absolute path on the PC)",
            hintText: r"C:\...\accounts\<handle>\tweets\YYYY\YYYY-MM\<ts>_<id>",
          ),
        ),
        const SizedBox(height: 12),
        if (_op == "all")
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text("Also run OCR"),
            value: _withOcr,
            onChanged: (v) => setState(() => _withOcr = v),
          ),
        const SizedBox(height: 12),
        FilledButton.icon(
          icon: const Icon(Icons.play_arrow),
          label: Text(_busy ? "Running..." : "Run on PC"),
          onPressed: _busy ? null : _run,
        ),
        const SizedBox(height: 24),
        if (_job != null) _JobCard(job: _job!),
        if (_lastJobId != null && _job == null)
          Text("job_id: $_lastJobId"),
      ],
    );
  }
}

class _JobCard extends StatelessWidget {
  final Job job;
  const _JobCard({required this.job});

  @override
  Widget build(BuildContext context) {
    Color color;
    switch (job.status) {
      case "done":
        color = Colors.green;
        break;
      case "failed":
        color = Colors.red;
        break;
      default:
        color = Colors.blue;
    }
    return Card(
      child: ListTile(
        leading: Icon(Icons.bolt, color: color),
        title: Text("${job.op} — ${job.status}"),
        subtitle: Text(
          "id=${job.id}"
          "${job.returncode == null ? '' : '  rc=${job.returncode}'}",
        ),
      ),
    );
  }
}
