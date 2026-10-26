enum QualityState { pass, warning, fail }

class CaptureCondition {
  final double stability;    // 0.0 -> 1.0 (ổn định con quay hồi chuyển)
  final double lightingLux;   // cường độ sáng quang học
  final double glareScore;     // 0.0 -> 1.0 (mức độ phản xạ lóa sáng)
  final double distanceCm;    // khoảng cách tiêu cự khuyến nghị

  const CaptureCondition({
    required this.stability,
    required this.lightingLux,
    required this.glareScore,
    required this.distanceCm,
  });

  QualityState get stabilityState => stability >= 0.85
      ? QualityState.pass
      : (stability >= 0.60 ? QualityState.warning : QualityState.fail);

  QualityState get lightState => (lightingLux >= 300 && lightingLux <= 1200)
      ? QualityState.pass
      : (lightingLux >= 150 ? QualityState.warning : QualityState.fail);

  QualityState get glareState => glareScore <= 0.25
      ? QualityState.pass
      : (glareScore <= 0.50 ? QualityState.warning : QualityState.fail);

  bool get isReadyToCapture =>
      stabilityState == QualityState.pass &&
      lightState != QualityState.fail &&
      glareState == QualityState.pass;
}

enum DeviceProfile {
  smartphone('Smartphone', 'ALIGN_SMARTPHONE'),
  keyboard('Bàn phím cơ / laptop', 'ALIGN_KEYBOARD'),
  laptop('Mặt phẳng Laptop', 'ALIGN_LAPTOP');

  final String label;
  final String code;
  const DeviceProfile(this.label, this.code);
}

enum InspectionStepType {
  front('Mặt trước', 'ALIGN_FRONT'),
  back('Mặt sau', 'ALIGN_BACK'),
  edgeTop('Cạnh trên', 'ALIGN_EDGE_TOP'),
  edgeBottom('Cạnh dưới', 'ALIGN_EDGE_BOT'),
  edgeLeft('Cạnh trái', 'ALIGN_EDGE_LEFT'),
  edgeRight('Cạnh phải', 'ALIGN_EDGE_RIGHT'),
  cameraIsland('Cụm camera', 'ALIGN_CAM_ISLAND');

  final String label;
  final String code;
  const InspectionStepType(this.label, this.code);
}
