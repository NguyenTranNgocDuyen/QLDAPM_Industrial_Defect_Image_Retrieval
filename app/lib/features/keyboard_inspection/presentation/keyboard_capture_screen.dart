import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../data/keyboard_inspection_api.dart';
import 'keyboard_result_screen.dart';

class KeyboardCaptureScreen extends StatefulWidget {
  const KeyboardCaptureScreen({super.key});

  @override
  State<KeyboardCaptureScreen> createState() => _KeyboardCaptureScreenState();
}

class _KeyboardCaptureScreenState extends State<KeyboardCaptureScreen> {
  final _picker = ImagePicker();
  bool _submitting = false;

  Future<void> _pick(ImageSource source) async {
    final photo = await _picker.pickImage(source: source, imageQuality: 95);
    if (photo == null || !mounted) return;
    setState(() => _submitting = true);
    try {
      final result = await KeyboardInspectionApi().inspect(File(photo.path));
      if (!mounted) return;
      await Navigator.push(context, MaterialPageRoute(builder: (_) => KeyboardResultScreen(result: result)));
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Không thể gửi ảnh bàn phím. Hãy thử lại.')));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Kiểm tra bàn phím')),
    body: Center(child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.keyboard_alt_outlined, size: 76),
        const SizedBox(height: 16),
        const Text('Chụp hoặc chọn ảnh bàn phím rõ, đủ sáng và thấy đầy đủ các hàng phím.', textAlign: TextAlign.center),
        const SizedBox(height: 24),
        if (_submitting) const CircularProgressIndicator() else Wrap(spacing: 12, children: [
          FilledButton.icon(onPressed: () => _pick(ImageSource.camera), icon: const Icon(Icons.camera_alt), label: const Text('Chụp ảnh')),
          OutlinedButton.icon(onPressed: () => _pick(ImageSource.gallery), icon: const Icon(Icons.photo_library), label: const Text('Chọn ảnh')),
        ]),
      ]),
    )),
  );
}
