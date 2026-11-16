class KeyboardInspectionResult {
  final String inspectionId;
  final String status;
  final bool hasDefect;
  final bool needsReview;
  final String? imageUrl;
  final List<String> reasons;
  final List<Map<String, dynamic>> defects;
  const KeyboardInspectionResult({required this.inspectionId, required this.status, required this.hasDefect, required this.needsReview, this.imageUrl, required this.reasons, required this.defects});
  factory KeyboardInspectionResult.fromJson(Map<String, dynamic> json) {
    final summary = (json['summary'] as Map?)?.cast<String, dynamic>() ?? {};
    final display = (json['displayImage'] as Map?)?.cast<String, dynamic>() ?? {};
    return KeyboardInspectionResult(inspectionId: json['inspectionId'] as String? ?? '', status: json['status'] as String? ?? 'processing_error', hasDefect: json['hasDefect'] == true, needsReview: summary['needsReview'] == true, imageUrl: display['url'] as String?, reasons: ((summary['reasons'] as List?) ?? []).map((value) => '$value').toList(), defects: ((json['defects'] as List?) ?? []).map((value) => (value as Map).cast<String, dynamic>()).toList());
  }
}
