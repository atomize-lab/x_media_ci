// Entry point.
//
// Bottom-nav with 4 sections (Browse / Remote / Local / Edit) plus a
// settings entry in the AppBar. All screens share the same
// `CiApi.instance` for HTTP.
import 'package:flutter/material.dart';

import 'api/ci_api.dart';
import 'screens/browse_screen.dart';
import 'screens/edit_screen.dart';
import 'screens/local_screen.dart';
import 'screens/remote_screen.dart';
import 'screens/settings_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await CiApi.instance.load();
  runApp(const XMediaCiApp());
}

class XMediaCiApp extends StatelessWidget {
  const XMediaCiApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "CiteSeal",
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      home: const HomeShell(),
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _titles = ["Browse", "Remote", "Local", "Edit"];
  static const _bodies = <Widget>[
    BrowseScreen(),
    RemoteScreen(),
    LocalScreen(),
    EditScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("CiteSeal — ${_titles[_index]}"),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
          ),
        ],
      ),
      body: SafeArea(child: _bodies[_index]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.folder), label: "Browse"),
          NavigationDestination(icon: Icon(Icons.bolt), label: "Remote"),
          NavigationDestination(icon: Icon(Icons.download), label: "Local"),
          NavigationDestination(icon: Icon(Icons.edit), label: "Edit"),
        ],
      ),
    );
  }
}
