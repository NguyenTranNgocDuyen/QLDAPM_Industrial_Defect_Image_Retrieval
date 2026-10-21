import 'package:flutter/foundation.dart';
import 'package:gal/gal.dart';

abstract class GallerySaverService {
  Future<void> saveImageBytes({
    required Uint8List bytes,
    required String fileName,
  });
}

class GalGallerySaverService implements GallerySaverService {
  const GalGallerySaverService();

  @override
  Future<void> saveImageBytes({
    required Uint8List bytes,
    required String fileName,
  }) async {
    try {
      await Gal.putImageBytes(bytes, name: fileName);
    } on GalException catch (e) {
      debugPrint('[GallerySaverService] GalException: ${e.type.message}');
      switch (e.type) {
        case GalExceptionType.accessDenied:
          throw const GallerySaverException(
            'Quyền truy cập thư viện ảnh bị từ chối. Vui lòng cấp quyền trong Cài đặt thiết bị.',
          );
        case GalExceptionType.notEnoughSpace:
          throw const GallerySaverException(
            'Bộ nhớ thiết bị không đủ để lưu ảnh kết quả.',
          );
        case GalExceptionType.notSupportedFormat:
          throw const GallerySaverException(
            'Định dạng ảnh này không được thiết bị hỗ trợ để lưu vào thư viện.',
          );
        default:
          throw GallerySaverException(
            'Lỗi khi lưu ảnh vào thư viện: ${e.type.message}',
          );
      }
    } catch (e) {
      debugPrint('[GallerySaverService] Unexpected error: $e');
      throw GallerySaverException('Không thể lưu ảnh vào thư viện: $e');
    }
  }
}

class GallerySaverException implements Exception {
  final String message;
  const GallerySaverException(this.message);

  @override
  String toString() => message;
}
