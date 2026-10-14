import 'package:flutter/material.dart';
import '../../../../core/theme/defect_theme_ext.dart';
import '../../models/defect_item.dart';

class DefectOverlayPainter extends CustomPainter {
  final List<DefectItem> defects;
  final String? selectedDefectId;
  final bool showLabels;
  final DefectThemeExtension defectColors;

  DefectOverlayPainter({
    required this.defects,
    required this.selectedDefectId,
    required this.showLabels,
    required this.defectColors,
  });

  Color _getColor(DefectSeverity severity) {
    switch (severity) {
      case DefectSeverity.minor:
        return defectColors.minorDefect;
      case DefectSeverity.moderate:
        return defectColors.moderateDefect;
      case DefectSeverity.critical:
        return defectColors.criticalDefect;
    }
  }

  @override
  void paint(Canvas canvas, Size size) {
    for (final defect in defects) {
      final isSelected = defect.id == selectedDefectId;
      final color = _getColor(defect.severity);

      // Chuyển relative bounding box (0.0 -> 1.0) sang toạ độ màn hình thực tế
      final rect = Rect.fromLTWH(
        defect.relativeBox.left * size.width,
        defect.relativeBox.top * size.height,
        defect.relativeBox.width * size.width,
        defect.relativeBox.height * size.height,
      );

      // 1. Vùng highlight bán trong suốt
      final fillPaint = Paint()
        ..color = color.withValues(alpha: isSelected ? 0.28 : 0.12)
        ..style = PaintingStyle.fill;
      canvas.drawRect(rect, fillPaint);

      // 2. Viền bounding box
      final strokePaint = Paint()
        ..color = color
        ..strokeWidth = isSelected ? 2.0 : 1.2
        ..style = PaintingStyle.stroke;
      canvas.drawRect(rect, strokePaint);

      // 3. Đánh dấu góc bounding box (Precision corner notches)
      final notchPaint = Paint()
        ..color = isSelected ? Colors.white : color
        ..strokeWidth = 2.5
        ..style = PaintingStyle.stroke;
      const notchSize = 6.0;

      // Top-Left corner
      canvas.drawLine(rect.topLeft, rect.topLeft + const Offset(notchSize, 0), notchPaint);
      canvas.drawLine(rect.topLeft, rect.topLeft + const Offset(0, notchSize), notchPaint);

      // Bottom-Right corner
      canvas.drawLine(rect.bottomRight, rect.bottomRight - const Offset(notchSize, 0), notchPaint);
      canvas.drawLine(rect.bottomRight, rect.bottomRight - const Offset(0, notchSize), notchPaint);

      // 4. Bảng nhãn hiển thị loại lỗi & thông số kích thước mm
      if (showLabels) {
        final labelText =
            '${defect.severity.symbol} ${defect.title} (${defect.lengthMm.toStringAsFixed(1)}mm)';
        final textSpan = TextSpan(
          text: labelText,
          style: TextStyle(
            color: Colors.white,
            fontSize: 9,
            fontWeight: FontWeight.bold,
            backgroundColor: color.withValues(alpha: 0.9),
          ),
        );
        final textPainter = TextPainter(
          text: textSpan,
          textDirection: TextDirection.ltr,
        )..layout();

        final labelOffset = Offset(
          rect.left.clamp(0.0, size.width - textPainter.width),
          (rect.top - 16).clamp(0.0, size.height - 16),
        );
        textPainter.paint(canvas, labelOffset);
      }
    }
  }

  @override
  bool shouldRepaint(covariant DefectOverlayPainter oldDelegate) {
    return oldDelegate.defects != defects ||
        oldDelegate.selectedDefectId != selectedDefectId ||
        oldDelegate.showLabels != showLabels;
  }
}
