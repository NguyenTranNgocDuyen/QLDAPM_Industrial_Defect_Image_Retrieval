import 'package:flutter/material.dart';

enum DefectSeverity {
  minor('Nhẹ', '○'),
  moderate('Trung bình', '▲'),
  critical('Nghiêm trọng', '■');

  final String label;
  final String symbol;
  const DefectSeverity(this.label, this.symbol);
}

class DefectItem {
  final String id;
  final String title;
  final String locationDesc;
  final double lengthMm;
  final double confidence; // 0.0 -> 1.0 (91% -> 0.91)
  final DefectSeverity severity;
  final Rect relativeBox; // 0.0 -> 1.0 relative coordinates (left, top, width, height)
  final bool isUserVerified;

  const DefectItem({
    required this.id,
    required this.title,
    required this.locationDesc,
    required this.lengthMm,
    required this.confidence,
    required this.severity,
    required this.relativeBox,
    this.isUserVerified = false,
  });

  DefectItem copyWith({
    String? id,
    String? title,
    String? locationDesc,
    double? lengthMm,
    double? confidence,
    DefectSeverity? severity,
    Rect? relativeBox,
    bool? isUserVerified,
  }) {
    return DefectItem(
      id: id ?? this.id,
      title: title ?? this.title,
      locationDesc: locationDesc ?? this.locationDesc,
      lengthMm: lengthMm ?? this.lengthMm,
      confidence: confidence ?? this.confidence,
      severity: severity ?? this.severity,
      relativeBox: relativeBox ?? this.relativeBox,
      isUserVerified: isUserVerified ?? this.isUserVerified,
    );
  }
}

enum CosmeticGrade {
  gradeA('Hạng A (99%)', 'Gần như mới, không trầy xước thấy được.'),
  gradeB('Hạng B (95%)', 'Xước dăm nhẹ viền hoặc mặt lưng, màn hình đẹp.'),
  gradeC('Hạng C (90%)', 'Trầy xước/cấn góc rõ ràng, không nứt kính.'),
  reject('Từ chối / Lỗi nặng', 'Kính nứt, móp biến dạng khung sườn.');

  final String label;
  final String description;
  const CosmeticGrade(this.label, this.description);
}

class InspectionRecord {
  final String id;
  final String deviceName;
  final String imei;
  final DateTime inspectedAt;
  final CosmeticGrade grade;
  final List<DefectItem> defects;
  final int totalScannedSurfaces;

  const InspectionRecord({
    required this.id,
    required this.deviceName,
    required this.imei,
    required this.inspectedAt,
    required this.grade,
    required this.defects,
    required this.totalScannedSurfaces,
  });
}
