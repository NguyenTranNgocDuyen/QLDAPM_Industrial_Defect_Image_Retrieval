import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../models/keyboard_inspection_result.dart';

class KeyboardInspectionApi {
  final String baseUrl;
  KeyboardInspectionApi({this.baseUrl = 'http://10.0.2.2:8080'});
  String assetUrl(String? path) => path == null || path.isEmpty ? '' : '$baseUrl$path';
  Future<KeyboardInspectionResult> inspect(File image, {String? deviceInfo}) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/keyboard-inspections'));
    request.files.add(await http.MultipartFile.fromPath('image', image.path));
    if (deviceInfo != null) request.fields['deviceInfo'] = deviceInfo;
    final response = await http.Response.fromStream(await request.send());
    if (response.statusCode >= 400) throw Exception('Không thể kiểm tra bàn phím.');
    return KeyboardInspectionResult.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }
  Future<List<KeyboardInspectionResult>> history() async {
    final response = await http.get(Uri.parse('$baseUrl/api/keyboard-inspections?size=50'));
    if (response.statusCode >= 400) throw Exception('Không thể tải lịch sử kiểm tra.');
    final root = jsonDecode(response.body) as Map<String, dynamic>;
    return ((root['content'] as List?) ?? []).map((value) => KeyboardInspectionResult.fromJson((value as Map).cast<String, dynamic>())).toList();
  }
}
