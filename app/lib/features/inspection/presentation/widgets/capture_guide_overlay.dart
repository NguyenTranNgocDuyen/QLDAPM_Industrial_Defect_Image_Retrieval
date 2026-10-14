import 'package:flutter/material.dart';
import '../../models/capture_condition.dart';

class CaptureGuideOverlay extends StatelessWidget {
  final DeviceProfile profile;
  final bool isReady;

  const CaptureGuideOverlay({
    super.key,
    required this.profile,
    required this.isReady,
  });

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: CustomPaint(
        painter: _GuideOverlayPainter(
          profile: profile,
          accentColor: isReady ? const Color(0xFFF59E0B) : const Color(0xFF5A6370),
        ),
        child: const SizedBox.expand(),
      ),
    );
  }
}

class _GuideOverlayPainter extends CustomPainter {
  final DeviceProfile profile;
  final Color accentColor;

  _GuideOverlayPainter({required this.profile, required this.accentColor});

  @override
  void paint(Canvas canvas, Size size) {
    final double targetWidth;
    final double targetHeight;

    switch (profile) {
      case DeviceProfile.smartphone:
        targetWidth = size.width * 0.76;
        targetHeight = targetWidth * 2.05;
        break;
      case DeviceProfile.keyboard:
        targetWidth = size.width * 0.90;
        targetHeight = targetWidth * 0.38;
        break;
      case DeviceProfile.laptop:
        targetWidth = size.width * 0.86;
        targetHeight = targetWidth * 0.65;
        break;
    }

    final rect = Rect.fromCenter(
      center: Offset(size.width / 2, size.height * 0.42),
      width: targetWidth,
      height: targetHeight,
    );

    final linePaint = Paint()
      ..color = accentColor
      ..strokeWidth = 2.0
      ..style = PaintingStyle.stroke;

    final dashPaint = Paint()
      ..color = accentColor.withOpacity(0.25)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;

    final rrect = RRect.fromRectAndRadius(rect, const Radius.circular(8));
    canvas.drawRRect(rrect, dashPaint);

    const cornerLen = 22.0;

    // Top-Left
    canvas.drawLine(rect.topLeft, rect.topLeft + const Offset(cornerLen, 0), linePaint);
    canvas.drawLine(rect.topLeft, rect.topLeft + const Offset(0, cornerLen), linePaint);

    // Top-Right
    canvas.drawLine(rect.topRight, rect.topRight + const Offset(-cornerLen, 0), linePaint);
    canvas.drawLine(rect.topRight, rect.topRight + const Offset(0, cornerLen), linePaint);

    // Bottom-Left
    canvas.drawLine(rect.bottomLeft, rect.bottomLeft + const Offset(cornerLen, 0), linePaint);
    canvas.drawLine(rect.bottomLeft, rect.bottomLeft + const Offset(0, -cornerLen), linePaint);

    // Bottom-Right
    canvas.drawLine(rect.bottomRight, rect.bottomRight + const Offset(-cornerLen, 0), linePaint);
    canvas.drawLine(rect.bottomRight, rect.bottomRight + const Offset(0, -cornerLen), linePaint);

    // Center Crosshair
    final center = rect.center;
    canvas.drawLine(center - const Offset(6, 0), center + const Offset(6, 0), dashPaint);
    canvas.drawLine(center - const Offset(0, 6), center + const Offset(0, 6), dashPaint);
  }

  @override
  bool shouldRepaint(covariant _GuideOverlayPainter oldDelegate) {
    return oldDelegate.accentColor != accentColor || oldDelegate.profile != profile;
  }
}
