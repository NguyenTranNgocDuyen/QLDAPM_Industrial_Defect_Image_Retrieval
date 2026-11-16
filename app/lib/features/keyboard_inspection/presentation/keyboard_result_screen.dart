import 'package:flutter/material.dart';
import '../data/keyboard_inspection_api.dart';
import '../models/keyboard_inspection_result.dart';

class KeyboardResultScreen extends StatelessWidget {
  final KeyboardInspectionResult result;
  const KeyboardResultScreen({super.key, required this.result});
  String get title => result.status == 'processing_error' ? 'Không thể xử lý ảnh' : result.status == 'insufficient_evidence' ? 'Cần kiểm tra thủ công' : result.hasDefect ? 'Đã phát hiện lỗi ngoại quan' : 'Không phát hiện lỗi ngoại quan trong ảnh';
  @override Widget build(BuildContext context) {
    final api = KeyboardInspectionApi(); final image = api.assetUrl(result.imageUrl);
    return Scaffold(appBar: AppBar(title: const Text('Kết quả kiểm tra bàn phím')), body: ListView(padding: const EdgeInsets.all(16), children: [
      if (image.isNotEmpty) ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.network(image, errorBuilder: (_, __, ___) => const SizedBox(height: 80, child: Center(child: Text('Không tải được ảnh đánh dấu.'))))),
      Card(child: Padding(padding: const EdgeInsets.all(16), child: Text(title, style: Theme.of(context).textTheme.titleMedium))),
      if (result.status == 'completed' && !result.hasDefect) const Text('Kết quả chỉ nói rằng không phát hiện lỗi ngoại quan trong ảnh đạt điều kiện đánh giá; không chứng minh bàn phím hoạt động bình thường.'),
      if (result.reasons.isNotEmpty) ...[const SizedBox(height: 12), ...result.reasons.map((reason) => Text('• $reason'))],
      ...result.defects.map((defect) => ListTile(leading: const Icon(Icons.warning_amber_rounded), title: Text('${defect['type']} — ${defect['severity']}'), subtitle: Text('${defect['reason'] ?? ''}\nĐộ tin cậy: ${defect['confidence'] ?? ''}'), isThreeLine: true)),
    ]));
  }
}
