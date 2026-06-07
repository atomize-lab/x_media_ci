// Browse screen: pull the list of accounts from the server and drill in.
//
//  /api/accounts                -> list of {handle, tweet_count}
//  /api/accounts/{handle}       -> {handle, months: [{key, count}]}
//  /api/tweet/{tweet_id}        -> TweetDetail
import 'package:flutter/material.dart';

import '../api/ci_api.dart';
import 'settings_screen.dart';

class BrowseScreen extends StatefulWidget {
  const BrowseScreen({super.key});

  @override
  State<BrowseScreen> createState() => _BrowseScreenState();
}

class _BrowseScreenState extends State<BrowseScreen> {
  late Future<List<Account>> _future;

  @override
  void initState() {
    super.initState();
    _future = (CiApi.instance.remoteEnabled && CiApi.instance.isConfigured)
        ? CiApi.instance.accounts()
        : Future.value(const []);
  }

  Future<void> _reload() async {
    setState(() {
      _future = (CiApi.instance.remoteEnabled && CiApi.instance.isConfigured)
          ? CiApi.instance.accounts()
          : Future.value(const []);
    });
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _reload,
      child: FutureBuilder<List<Account>>(
        future: _future,
        builder: (context, snap) {
          if (!CiApi.instance.remoteEnabled) {
            return ListView(
              children: [
                const SizedBox(height: 140),
                const Icon(Icons.cloud_off, size: 48),
                const SizedBox(height: 12),
                const Center(child: Text("Browse/Remote/Edit 默认关闭（不依赖电脑）")),
                const SizedBox(height: 8),
                Center(
                  child: Text(
                    "电脑服务已关闭。只用手机请去 Local 标签页。",
                    style: const TextStyle(fontFamily: "monospace", fontSize: 12),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 12),
                Center(
                  child: FilledButton(
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const SettingsScreen()),
                    ),
                    child: const Text("去开启电脑服务"),
                  ),
                ),
                const SizedBox(height: 12),
                const Center(child: Text("要浏览电脑上的 CI 目录，再去 Settings 开启并配置。")),
              ],
            );
          }
          if (!CiApi.instance.isConfigured) {
            return ListView(
              children: [
                const SizedBox(height: 140),
                const Icon(Icons.settings_ethernet, size: 48),
                const SizedBox(height: 12),
                const Center(child: Text("已开启电脑服务，但未设置 Server URL")),
                const SizedBox(height: 8),
                Center(
                  child: Text(
                    "请在 Settings 里填 http://<PC_IP>:8765",
                    style: const TextStyle(fontFamily: "monospace", fontSize: 12),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 12),
                Center(
                  child: FilledButton(
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const SettingsScreen()),
                    ),
                    child: const Text("去设置"),
                  ),
                ),
              ],
            );
          }
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return _ErrorView(message: "${snap.error}", onRetry: _reload);
          }
          final items = snap.data ?? const [];
          if (items.isEmpty) {
            return ListView(children: const [
              SizedBox(height: 200),
              Center(child: Text("No accounts yet. Run `make fix` first.")),
            ]);
          }
          return ListView.separated(
            itemCount: items.length,
            separatorBuilder: (_, __) => const Divider(height: 0),
            itemBuilder: (context, i) {
              final a = items[i];
              return ListTile(
                leading: const Icon(Icons.account_circle_outlined),
                title: Text(a.handle),
                subtitle: Text("${a.tweetCount} tweet(s)"),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => AccountScreen(handle: a.handle),
                  ));
                },
              );
            },
          );
        },
      ),
    );
  }
}

class AccountScreen extends StatelessWidget {
  final String handle;
  const AccountScreen({super.key, required this.handle});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text("@$handle")),
      body: FutureBuilder<AccountDetail>(
        future: CiApi.instance.accountDetail(handle),
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return _ErrorView(message: "${snap.error}", onRetry: () {
              Navigator.of(context).pushReplacement(MaterialPageRoute(
                builder: (_) => AccountScreen(handle: handle),
              ));
            });
          }
          final d = snap.data!;
          if (d.months.isEmpty) {
            return const Center(child: Text("No months."));
          }
          return ListView.separated(
            itemCount: d.months.length,
            separatorBuilder: (_, __) => const Divider(height: 0),
            itemBuilder: (context, i) {
              final m = d.months[i];
              return ExpansionTile(
                title: Text(m.key),
                subtitle: Text("${m.count} tweet(s)"),
                children: [
                  // For brevity we just point the user at the JSONL index.
                  // The "Tweets under this month" screen can be added by
                  // paginating `/api/index/tweets?handle=<handle>`.
                  Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Text(
                      "See ${CiApi.instance.baseUrl}/api/index/tweets?handle=$handle",
                      style: const TextStyle(fontFamily: "monospace"),
                    ),
                  ),
                ],
              );
            },
          );
        },
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton(onPressed: onRetry, child: const Text("Retry")),
          ],
        ),
      ),
    );
  }
}
