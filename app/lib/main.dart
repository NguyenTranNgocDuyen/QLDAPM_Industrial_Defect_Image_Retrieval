import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme/app_theme.dart';
import 'features/inspection/presentation/capture_screen.dart';
import 'features/keyboard_inspection/presentation/keyboard_capture_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    const ProviderScope(
      child: CosmeticInspectorApp(),
    ),
  );
}

class CosmeticInspectorApp extends StatelessWidget {
  const CosmeticInspectorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Cosmetic Inspector',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.dark, // Lab tool mặc định nền tối xám than
      home: const InspectionHomeScreen(),
    );
  }
}

class InspectionHomeScreen extends StatelessWidget {
  const InspectionHomeScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Kiểm tra ngoại quan')),
    body: Center(child: Wrap(spacing: 12, runSpacing: 12, children: [
      FilledButton.icon(onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const CaptureScreen())), icon: const Icon(Icons.phone_android), label: const Text('Kiểm tra điện thoại')),
      OutlinedButton.icon(onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const KeyboardCaptureScreen())), icon: const Icon(Icons.keyboard), label: const Text('Kiểm tra bàn phím')),
    ])),
  );
}
