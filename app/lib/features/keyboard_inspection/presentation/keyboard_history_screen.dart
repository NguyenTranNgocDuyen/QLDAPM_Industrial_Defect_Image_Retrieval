import 'package:flutter/material.dart';
import '../data/keyboard_inspection_api.dart';
import '../models/keyboard_inspection_result.dart';
import 'keyboard_result_screen.dart';

class KeyboardHistoryScreen extends StatefulWidget { const KeyboardHistoryScreen({super.key}); @override State<KeyboardHistoryScreen> createState() => _KeyboardHistoryScreenState(); }
class _KeyboardHistoryScreenState extends State<KeyboardHistoryScreen> {
  late Future<List<KeyboardInspectionResult>> _items;
  @override void initState() { super.initState(); _items = KeyboardInspectionApi().history(); }
  @override Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Lịch sử kiểm tra bàn phím')), body: FutureBuilder<List<KeyboardInspectionResult>>(future: _items, builder: (_, snapshot) {
    if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
    if (snapshot.hasError) return Center(child: Text('Không tải được lịch sử: ${snapshot.error}'));
    final items = snapshot.data ?? []; if (items.isEmpty) return const Center(child: Text('Chưa có lần kiểm tra nào.'));
    return RefreshIndicator(onRefresh: () async => setState(() => _items = KeyboardInspectionApi().history()), child: ListView(children: items.map((item) => ListTile(title: Text(item.status), subtitle: Text(item.hasDefect ? 'Có lỗi ngoại quan' : item.needsReview ? 'Cần kiểm tra thủ công' : 'Không phát hiện lỗi trong ảnh'), trailing: const Icon(Icons.chevron_right), onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => KeyboardResultScreen(result: item)))).toList()));
  }));
}
