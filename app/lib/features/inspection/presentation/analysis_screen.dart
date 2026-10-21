import 'dart:math';
import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../data/damage_api.dart';
import '../models/capture_condition.dart';
import 'result_screen.dart';

String _generateUuidV4() {
  final rnd = Random.secure();
  final bytes = List<int>.generate(16, (_) => rnd.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20, 32)}';
}

class AnalysisScreen extends StatefulWidget {
  final String deviceName;
  final String deviceImei;
  final Map<InspectionStepType, String> capturedImages;
  const AnalysisScreen({
    super.key,
    required this.deviceName,
    required this.deviceImei,
    this.capturedImages = const {},
  });
  @override
  State<AnalysisScreen> createState() => _AnalysisScreenState();
}

class _AnalysisScreenState extends State<AnalysisScreen> {
  final _api = DamageApi();
  bool _running = false;
  String _phase = 'Sẵn sàng phân tích ảnh đã chụp';
  int _done = 0;

  Future<void> _analyze() async {
    setState(() => _running = true);
    final results = <InspectionStepType, Map<String, dynamic>>{};
    final sessionId = _generateUuidV4();
    for (final entry in widget.capturedImages.entries) {
      if (!mounted) return;
      final elapsed = Stopwatch()..start();
      debugPrint(
        '[DamageApi] ${entry.key.name}: bắt đầu gửi tới ${DamageApi.baseUrl}',
      );
      setState(
        () => _phase =
            'Đang phân tích ${entry.key.label.toLowerCase()} ở độ phân giải gốc…',
      );
      try {
        results[entry.key] = await _api.analyze(
          entry.value,
          entry.key.name,
          sessionId: sessionId,
          deviceInfo: widget.deviceName,
        );
        debugPrint(
          '[DamageApi] ${entry.key.name}: hoàn tất sau ${elapsed.elapsedMilliseconds} ms, '
          'status=${results[entry.key]?['status']}',
        );
      } catch (error, stack) {
        if (!mounted) return;
        final failure = error is DamageApiException
            ? error
            : const DamageApiException(
                'unexpected_error',
                'Không nhận được kết quả hợp lệ. Hãy kiểm tra kết nối và thử lại.',
              );
        debugPrint('[DamageApi] ${failure.code}: $error');
        debugPrintStack(stackTrace: stack);
        results[entry.key] = {
          'success': false,
          'error': {'code': failure.code, 'message': failure.message},
          'severity': {
            'status': 'insufficient_evidence',
            'needs_review': true,
            'estimated_severity': null,
            'reasons': ['connection_or_processing_error'],
          },
          'damage': {'status': 'processing_error'},
        };
      }
      if (!mounted) return;
      setState(() => _done++);
    }
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => ResultScreen(
          deviceName: widget.deviceName,
          deviceImei: widget.deviceImei,
          results: results,
        ),
      ),
    );
  }

  @override
  void dispose() {
    _api.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: AppColors.darkCanvas,
    appBar: AppBar(title: Text(widget.deviceName)),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(_phase, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 20),
          if (_running) ...[
            const LinearProgressIndicator(),
            const SizedBox(height: 12),
            Text(
              'Đã xử lý $_done / ${widget.capturedImages.length} ảnh. Vui lòng giữ màn hình mở.',
            ),
          ] else ...[
            Text(
              '${widget.capturedImages.length} ảnh sẽ được gửi tới máy chủ để phân tích.',
            ),
            const SizedBox(height: 16),
            const Text(
              'Đánh giá từng mặt quan sát bằng hình học. Các ngưỡng thử nghiệm chưa được kiểm chứng bằng nhãn mức độ của con người.',
            ),
            const SizedBox(height: 16),
            const Text(
              'Tự xác định vùng hư hại và mức Nhẹ/Vừa/Nặng theo hình ảnh. Không cần nhập dòng máy hoặc kích thước. Ảnh thiếu phần có thể nhận mức sơ bộ trên vùng nhìn thấy, kèm cảnh báo cần kiểm tra.',
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: widget.capturedImages.isEmpty ? null : _analyze,
              icon: const Icon(Icons.analytics_outlined),
              label: const Text('Phân tích ảnh'),
            ),
          ],
        ],
      ),
    ),
  );
}
