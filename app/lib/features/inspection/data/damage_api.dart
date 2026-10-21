import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import '../models/scan_history_model.dart';

class DamageApiException implements Exception {
  final String code;
  final String message;
  const DamageApiException(this.code, this.message);
  @override
  String toString() => message;
}

class DamageApi {
  static const _configuredBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8080',
  );

  static String normalizeBaseUrl(String raw) {
    var cleaned = raw.trim();
    while (cleaned.endsWith('/')) {
      cleaned = cleaned.substring(0, cleaned.length - 1);
    }
    if (cleaned.isEmpty) {
      return 'http://10.0.2.2:8080';
    }
    if (!cleaned.startsWith('http://') && !cleaned.startsWith('https://')) {
      cleaned = 'http://$cleaned';
    }
    final uri = Uri.tryParse(cleaned);
    if (uri != null && !uri.hasPort && uri.scheme == 'http') {
      // Backend Spring Boot runs on port 8080 by default
      return 'http://${uri.host}:8080${uri.path}';
    }
    return cleaned;
  }

  static String get baseUrl => normalizeBaseUrl(_configuredBaseUrl);

  final http.Client _client;
  DamageApi({http.Client? client}) : _client = client ?? http.Client();

  Future<void> checkConnection() async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/api/health'))
          .timeout(const Duration(seconds: 8));
      if (response.statusCode != 200) {
        throw DamageApiException(
          'backend_unavailable',
          'BE tại $baseUrl chưa sẵn sàng (HTTP ${response.statusCode}).',
        );
      }
      final body = jsonDecode(response.body);
      if (body is! Map || body['status'] != 'UP') {
        throw const DamageApiException(
          'invalid_backend',
          'Địa chỉ API chưa trả đúng trạng thái BE.',
        );
      }
    } on TimeoutException {
      throw DamageApiException(
        'connection_timeout',
        'Không kết nối được BE tại $baseUrl trong 8 giây. Kiểm tra địa chỉ API và kết nối USB/Wi-Fi.',
      );
    } on http.ClientException {
      throw DamageApiException(
        'connection_failed',
        'Không kết nối được BE tại $baseUrl. Kiểm tra địa chỉ API và kết nối USB/Wi-Fi.',
      );
    } on FormatException {
      throw const DamageApiException(
        'invalid_backend',
        'Địa chỉ API chưa trả đúng dữ liệu BE.',
      );
    }
  }

  static (String mimeType, String filename) detectMimeAndFilename(
    String path,
    List<int> bytes,
  ) {
    if (bytes.length >= 8) {
      if (bytes[0] == 0x89 &&
          bytes[1] == 0x50 &&
          bytes[2] == 0x4E &&
          bytes[3] == 0x47) {
        final name = path.toLowerCase().endsWith('.png')
            ? path.split(RegExp(r'[\\/]')).last
            : 'image.png';
        return ('image/png', name);
      }
      if (bytes[0] == 0xFF && bytes[1] == 0xD8 && bytes[2] == 0xFF) {
        final name = path.toLowerCase().endsWith('.jpg') ||
                path.toLowerCase().endsWith('.jpeg')
            ? path.split(RegExp(r'[\\/]')).last
            : 'image.jpg';
        return ('image/jpeg', name);
      }
      if (bytes[0] == 0x52 &&
          bytes[1] == 0x49 &&
          bytes[2] == 0x46 &&
          bytes[3] == 0x46 &&
          bytes.length >= 12 &&
          bytes[8] == 0x57 &&
          bytes[9] == 0x45 &&
          bytes[10] == 0x42 &&
          bytes[11] == 0x50) {
        final name = path.toLowerCase().endsWith('.webp')
            ? path.split(RegExp(r'[\\/]')).last
            : 'image.webp';
        return ('image/webp', name);
      }
      if (bytes.length >= 12 &&
          bytes[4] == 0x66 &&
          bytes[5] == 0x74 &&
          bytes[6] == 0x79 &&
          bytes[7] == 0x70) {
        final brand =
            String.fromCharCodes(bytes.sublist(8, 12)).toLowerCase();
        if (brand.contains('heic') ||
            brand.contains('heif') ||
            brand.contains('mif1')) {
          throw const DamageApiException(
            'unsupported_format',
            'Định dạng HEIC/HEIF chưa được máy chủ hỗ trợ. Vui lòng chọn ảnh JPEG, PNG hoặc WebP.',
          );
        }
      }
    }
    final lower = path.toLowerCase();
    if (lower.endsWith('.heic') || lower.endsWith('.heif')) {
      throw const DamageApiException(
        'unsupported_format',
        'Định dạng HEIC/HEIF chưa được máy chủ hỗ trợ. Vui lòng chọn ảnh JPEG, PNG hoặc WebP.',
      );
    }
    if (lower.endsWith('.webp')) {
      return ('image/webp', path.split(RegExp(r'[\\/]')).last);
    }
    if (lower.endsWith('.png')) {
      return ('image/png', path.split(RegExp(r'[\\/]')).last);
    }
    final name = lower.endsWith('.jpg') || lower.endsWith('.jpeg')
        ? path.split(RegExp(r'[\\/]')).last
        : 'capture.jpg';
    return ('image/jpeg', name);
  }

  Future<Map<String, dynamic>> analyze(
    String path,
    String surface, {
    double? aspectRatio,
    bool fullSurfaceConfirmed = false,
    Uint8List? providedBytes,
    String? sessionId,
    String? deviceInfo,
  }) async {
    await checkConnection();
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/detections'),
    );
    request.fields.addAll({
      'surface': surface,
      'fullSurfaceConfirmed': '$fullSurfaceConfirmed',
      if (aspectRatio != null) 'surfaceAspectRatio': '$aspectRatio',
      if (sessionId != null) 'sessionId': sessionId,
      if (deviceInfo != null) 'deviceInfo': deviceInfo,
    });
    late final List<int> imageBytes;
    if (providedBytes != null && providedBytes.isNotEmpty) {
      imageBytes = providedBytes;
    } else {
      try {
        imageBytes = await XFile(path).readAsBytes();
      } catch (_) {
        throw const DamageApiException(
          'image_unavailable',
          'Không đọc được ảnh đã chọn/chụp. Hãy thử lại.',
        );
      }
    }

    if (imageBytes.length > 25 * 1024 * 1024) {
      throw const DamageApiException(
        'payload_too_large',
        'Dung lượng ảnh vượt quá giới hạn 25 MB của máy chủ. Vui lòng chọn ảnh khác.',
      );
    }

    final (mime, filename) = detectMimeAndFilename(path, imageBytes);
    final parts = mime.split('/');
    request.files.add(
      http.MultipartFile.fromBytes(
        'image',
        imageBytes,
        filename: filename,
        contentType: MediaType(parts[0], parts[1]),
      ),
    );
    late final http.Response response;
    try {
      response = await (() async => http.Response.fromStream(
        await _client.send(request),
      ))().timeout(const Duration(minutes: 6));
    } on TimeoutException {
      throw const DamageApiException(
        'processing_timeout',
        'Đã quá thời gian gửi/xử lý ảnh. Kiểm tra log BE và Python rồi thử lại.',
      );
    } on http.ClientException {
      throw DamageApiException(
        'connection_lost',
        'Mất kết nối tới BE tại $baseUrl khi gửi/nhận ảnh.',
      );
    }
    if (response.statusCode != 200) {
      throw DamageApiException(
        'http_error',
        'BE trả HTTP ${response.statusCode}. Kiểm tra log BE/Python; chưa có kết quả hợp lệ.',
      );
    }
    late final Map<String, dynamic> result;
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) throw const FormatException();
      result = decoded;
    } on FormatException {
      throw const DamageApiException(
        'invalid_response',
        'BE trả kết quả không đúng định dạng.',
      );
    }
    if (result['severity'] is! Map || result['damage'] is! Map) {
      throw const DamageApiException(
        'invalid_response',
        'Máy chủ thiếu dữ liệu đánh giá.',
      );
    }
    return result;
  }

  Future<List<ScanDateGroup>> getScanDates() async {
    final uri = Uri.parse(baseUrl).resolve('/api/scans/dates');
    late final http.Response response;
    try {
      response = await _client.get(uri).timeout(const Duration(seconds: 15));
    } on TimeoutException {
      throw const DamageApiException(
        'connection_timeout',
        'Hết thời gian tải danh sách ngày từ máy chủ.',
      );
    } on http.ClientException {
      throw DamageApiException(
        'connection_failed',
        'Không thể kết nối máy chủ tại $baseUrl để tải danh sách ngày.',
      );
    }
    if (response.statusCode != 200) {
      throw DamageApiException(
        'http_error',
        'Máy chủ trả mã lỗi ${response.statusCode} khi tải danh sách ngày.',
      );
    }
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is! List) throw const FormatException();
      return decoded
          .whereType<Map>()
          .map((m) => ScanDateGroup.fromJson(Map<String, dynamic>.from(m)))
          .toList();
    } catch (_) {
      throw const DamageApiException(
        'invalid_response',
        'Dữ liệu ngày trả về không hợp lệ.',
      );
    }
  }

  Future<List<InspectionSessionItem>> getInspectionSessions({String? date}) async {
    var uri = Uri.parse(baseUrl).resolve('/api/scans/sessions');
    if (date != null && date.isNotEmpty) {
      uri = uri.replace(queryParameters: {'date': date});
    }
    late final http.Response response;
    try {
      response = await _client.get(uri).timeout(const Duration(seconds: 15));
    } on TimeoutException {
      throw const DamageApiException(
        'connection_timeout',
        'Hết thời gian tải các lượt quét từ máy chủ.',
      );
    } on http.ClientException {
      throw DamageApiException(
        'connection_failed',
        'Không thể kết nối máy chủ tại $baseUrl để tải các lượt quét.',
      );
    }
    if (response.statusCode != 200) {
      throw DamageApiException(
        'http_error',
        'Máy chủ trả mã lỗi ${response.statusCode} khi tải các lượt quét.',
      );
    }
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is! List) throw const FormatException();
      return decoded
          .whereType<Map>()
          .map((m) => InspectionSessionItem.fromJson(Map<String, dynamic>.from(m)))
          .toList();
    } catch (_) {
      throw const DamageApiException(
        'invalid_response',
        'Dữ liệu các lượt quét trả về không hợp lệ.',
      );
    }
  }

  Future<ScanHistoryPage> getScanHistory({
    int page = 0,
    int size = 20,
    String sortBy = 'createdAt',
    String sortDir = 'desc',
    bool? hasDefect,
  }) async {
    final queryParams = <String, String>{
      'page': '$page',
      'size': '$size',
      'sortBy': sortBy,
      'sortDir': sortDir,
      if (hasDefect != null) 'hasDefect': '$hasDefect',
    };
    final uri = Uri.parse(baseUrl).replace(
      path: '/api/scans',
      queryParameters: queryParams,
    );
    late final http.Response response;
    try {
      response = await _client.get(uri).timeout(const Duration(seconds: 15));
    } on TimeoutException {
      throw const DamageApiException(
        'connection_timeout',
        'Hết thời gian kết nối máy chủ khi tải lịch sử. Kiểm tra mạng và thử lại.',
      );
    } on http.ClientException {
      throw DamageApiException(
        'connection_failed',
        'Không thể kết nối máy chủ tại $baseUrl để tải lịch sử quét.',
      );
    }
    if (response.statusCode != 200) {
      throw DamageApiException(
        'http_error',
        'Máy chủ trả mã lỗi HTTP ${response.statusCode} khi tải lịch sử.',
      );
    }
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException();
      }
      return ScanHistoryPage.fromJson(decoded);
    } on FormatException {
      throw const DamageApiException(
        'invalid_response',
        'Dữ liệu lịch sử từ máy chủ không đúng định dạng.',
      );
    }
  }

  Future<Map<String, dynamic>> getScanDetail(String scanId) async {
    final uri = Uri.parse(baseUrl).resolve('/api/scans/$scanId');
    late final http.Response response;
    try {
      response = await _client.get(uri).timeout(const Duration(seconds: 15));
    } on TimeoutException {
      throw const DamageApiException(
        'connection_timeout',
        'Hết thời gian tải chi tiết quét từ máy chủ.',
      );
    } on http.ClientException {
      throw DamageApiException(
        'connection_failed',
        'Không thể kết nối máy chủ tại $baseUrl để tải chi tiết quét.',
      );
    }
    if (response.statusCode == 404) {
      throw DamageApiException(
        'scan_not_found',
        'Không tìm thấy bản ghi quét $scanId trên máy chủ (HTTP 404).',
      );
    }
    if (response.statusCode != 200) {
      throw DamageApiException(
        'http_error',
        'Máy chủ trả mã lỗi HTTP ${response.statusCode} khi tải chi tiết.',
      );
    }
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) throw const FormatException();
      return decoded;
    } on FormatException {
      throw const DamageApiException(
        'invalid_response',
        'Dữ liệu chi tiết quét từ máy chủ không đúng định dạng.',
      );
    }
  }

  Future<Uint8List> downloadAssetBytes(String assetPathOrUrl) async {
    final uri = Uri.parse(baseUrl).resolve(assetPathOrUrl);
    late final http.Response response;
    try {
      response = await _client.get(uri).timeout(const Duration(seconds: 30));
    } on TimeoutException {
      throw const DamageApiException(
        'download_timeout',
        'Đã quá thời gian tải ảnh từ máy chủ. Vui lòng thử lại.',
      );
    } on http.ClientException {
      throw DamageApiException(
        'connection_error',
        'Không thể kết nối máy chủ để tải ảnh. Kiểm tra kết nối mạng.',
      );
    }
    if (response.statusCode == 404) {
      throw const DamageApiException(
        'asset_not_found',
        'Ảnh kết quả không còn tồn tại trên máy chủ (HTTP 404).',
      );
    }
    if (response.statusCode != 200) {
      throw DamageApiException(
        'download_failed',
        'Tải ảnh thất bại với mã lỗi HTTP ${response.statusCode}.',
      );
    }
    return response.bodyBytes;
  }

  static String assetUrl(String path) =>
      Uri.parse(baseUrl).resolve(path).toString();
  void close() => _client.close();
}
