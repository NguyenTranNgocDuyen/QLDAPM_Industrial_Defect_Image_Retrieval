import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

/// Kết quả trả về từ CNN endpoint.
class CnnResult {
  final String label;          // "normal" | "defective"
  final double confidence;     // 0.0 – 1.0
  final double preprocessingMs;
  final double inferenceMs;

  const CnnResult({
    required this.label,
    required this.confidence,
    required this.preprocessingMs,
    required this.inferenceMs,
  });

  factory CnnResult.fromJson(Map<String, dynamic> json) => CnnResult(
        label: json['label'] as String,
        confidence: (json['confidence'] as num).toDouble(),
        preprocessingMs: (json['preprocessing_ms'] as num).toDouble(),
        inferenceMs: (json['inference_ms'] as num).toDouble(),
      );

  bool get isDefective => label == 'defective';
}

/// Exception ném ra khi không kết nối được FastAPI server.
class InspectionApiException implements Exception {
  final String message;
  const InspectionApiException(this.message);

  @override
  String toString() => 'InspectionApiException: $message';
}

/// Service gọi FastAPI local server (uvicorn ui.local_api:app --port 8000).
class InspectionApiService {
  static const String _baseUrl = 'http://127.0.0.1:8000';
  static const Duration _timeout = Duration(seconds: 30);

  /// Kiểm tra server có đang chạy không.
  static Future<bool> isServerAlive() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/health'))
          .timeout(_timeout);
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Gửi ảnh lên server, nhận kết quả CNN.
  ///
  /// Throws [InspectionApiException] nếu:
  /// - Server không phản hồi (connection refused / timeout)
  /// - Server trả HTTP error (model chưa load, ảnh lỗi…)
  static Future<CnnResult> predict(File imageFile) async {
    final uri = Uri.parse('$_baseUrl/predict');
    final request = http.MultipartRequest('POST', uri);

    request.files.add(
      await http.MultipartFile.fromPath('image', imageFile.path),
    );

    http.StreamedResponse streamedResponse;
    try {
      streamedResponse = await request.send().timeout(_timeout);
    } on SocketException catch (e) {
      throw InspectionApiException(
        'Không kết nối được model server ($e). '
        'Hãy chạy: uvicorn ui.local_api:app --port 8000',
      );
    } on Exception catch (e) {
      throw InspectionApiException('Lỗi kết nối: $e');
    }

    final body = await streamedResponse.stream.bytesToString();

    if (streamedResponse.statusCode == 503) {
      throw const InspectionApiException(
        'Model chưa được load trên server. '
        'Hãy train model: python -m model.train --filter-name gaussian',
      );
    }

    if (streamedResponse.statusCode != 200) {
      throw InspectionApiException(
        'Server trả lỗi ${streamedResponse.statusCode}: $body',
      );
    }

    try {
      final json = jsonDecode(body) as Map<String, dynamic>;
      return CnnResult.fromJson(json);
    } catch (e) {
      throw InspectionApiException('Không parse được phản hồi: $body');
    }
  }
}
