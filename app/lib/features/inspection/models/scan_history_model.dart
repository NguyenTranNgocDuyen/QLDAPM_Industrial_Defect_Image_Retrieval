class ScanSummaryItem {
  final String scanId;
  final String? originalFilename;
  final String? displayImageUrl;
  final String? sourceImageUrl;
  final bool? hasDefect;
  final int detectionCount;
  final String status;
  final String? surface;
  final String? estimatedSeverity;
  final bool? needsReview;
  final double? totalMs;
  final DateTime? createdAt;

  const ScanSummaryItem({
    required this.scanId,
    this.originalFilename,
    this.displayImageUrl,
    this.sourceImageUrl,
    this.hasDefect,
    this.detectionCount = 0,
    required this.status,
    this.surface,
    this.estimatedSeverity,
    this.needsReview,
    this.totalMs,
    this.createdAt,
  });

  factory ScanSummaryItem.fromJson(Map<String, dynamic> json) {
    DateTime? parsedDate;
    final dateStr = json['createdAt'] as String?;
    if (dateStr != null) {
      parsedDate = DateTime.tryParse(dateStr)?.toLocal();
    }

    return ScanSummaryItem(
      scanId: (json['scanId'] ?? '').toString(),
      originalFilename: json['originalFilename'] as String?,
      displayImageUrl: json['displayImageUrl'] as String?,
      sourceImageUrl: json['sourceImageUrl'] as String?,
      hasDefect: json['hasDefect'] as bool?,
      detectionCount: (json['detectionCount'] as num?)?.toInt() ?? 0,
      status: (json['status'] ?? 'unknown').toString(),
      surface: json['surface'] as String?,
      estimatedSeverity: json['estimatedSeverity'] as String?,
      needsReview: json['needsReview'] as bool?,
      totalMs: (json['totalMs'] as num?)?.toDouble(),
      createdAt: parsedDate,
    );
  }

  String get surfaceLabel {
    switch (surface?.toLowerCase()) {
      case 'front':
        return 'Mặt trước';
      case 'back':
        return 'Mặt sau';
      default:
        return 'Chưa xác định mặt';
    }
  }

  String get shortScanId =>
      scanId.length >= 8 ? scanId.substring(0, 8) : scanId;
}

class ScanDateGroup {
  final String dateString;
  final DateTime date;
  final int sessionCount;
  final int scanCount;
  final int hasDefectCount;

  const ScanDateGroup({
    required this.dateString,
    required this.date,
    required this.sessionCount,
    required this.scanCount,
    required this.hasDefectCount,
  });

  factory ScanDateGroup.fromJson(Map<String, dynamic> json) {
    final dStr = (json['date'] ?? '').toString();
    DateTime parsed;
    try {
      parsed = DateTime.parse(dStr);
    } catch (_) {
      parsed = DateTime.now();
    }
    return ScanDateGroup(
      dateString: dStr,
      date: parsed,
      sessionCount: (json['sessionCount'] as num?)?.toInt() ?? 0,
      scanCount: (json['scanCount'] as num?)?.toInt() ?? 0,
      hasDefectCount: (json['hasDefectCount'] as num?)?.toInt() ?? 0,
    );
  }

  String get displayTitle {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final groupDay = DateTime(date.year, date.month, date.day);
    final diff = today.difference(groupDay).inDays;

    final d = date.day.toString().padLeft(2, '0');
    final m = date.month.toString().padLeft(2, '0');
    final y = date.year;

    if (diff == 0) {
      return 'Hôm nay ($d/$m/$y)';
    } else if (diff == 1) {
      return 'Hôm qua ($d/$m/$y)';
    } else {
      return '$d/$m/$y';
    }
  }
}

class InspectionSessionItem {
  final String sessionId;
  final DateTime? createdAt;
  final String? deviceInfo;
  final bool? hasDefect;
  final String? overallSeverity;
  final bool? needsReview;
  final ScanSummaryItem? frontScan;
  final ScanSummaryItem? backScan;
  final List<ScanSummaryItem> otherScans;

  const InspectionSessionItem({
    required this.sessionId,
    this.createdAt,
    this.deviceInfo,
    this.hasDefect,
    this.overallSeverity,
    this.needsReview,
    this.frontScan,
    this.backScan,
    this.otherScans = const [],
  });

  factory InspectionSessionItem.fromJson(Map<String, dynamic> json) {
    DateTime? parsedDate;
    final dateStr = json['createdAt'] as String?;
    if (dateStr != null) {
      parsedDate = DateTime.tryParse(dateStr)?.toLocal();
    }

    ScanSummaryItem? front;
    if (json['frontScan'] is Map) {
      front = ScanSummaryItem.fromJson(Map<String, dynamic>.from(json['frontScan'] as Map));
    }
    ScanSummaryItem? back;
    if (json['backScan'] is Map) {
      back = ScanSummaryItem.fromJson(Map<String, dynamic>.from(json['backScan'] as Map));
    }

    final others = <ScanSummaryItem>[];
    if (json['otherScans'] is List) {
      for (final o in json['otherScans'] as List) {
        if (o is Map) {
          others.add(ScanSummaryItem.fromJson(Map<String, dynamic>.from(o)));
        }
      }
    }

    return InspectionSessionItem(
      sessionId: (json['sessionId'] ?? '').toString(),
      createdAt: parsedDate,
      deviceInfo: json['deviceInfo'] as String?,
      hasDefect: json['hasDefect'] as bool?,
      overallSeverity: json['overallSeverity'] as String?,
      needsReview: json['needsReview'] as bool?,
      frontScan: front,
      backScan: back,
      otherScans: others,
    );
  }

  String get shortSessionId =>
      sessionId.length >= 8 ? sessionId.substring(0, 8) : sessionId;

  int get totalPhotos {
    var count = 0;
    if (frontScan != null) count++;
    if (backScan != null) count++;
    count += otherScans.length;
    return count;
  }
}

class ScanHistoryPage {
  final List<ScanSummaryItem> items;
  final int pageNumber;
  final int pageSize;
  final int totalElements;
  final int totalPages;
  final bool isLast;
  final bool isEmpty;

  const ScanHistoryPage({
    required this.items,
    required this.pageNumber,
    required this.pageSize,
    required this.totalElements,
    required this.totalPages,
    required this.isLast,
    required this.isEmpty,
  });

  factory ScanHistoryPage.fromJson(Map<String, dynamic> json) {
    final rawList = json['content'];
    final items = <ScanSummaryItem>[];
    if (rawList is List) {
      for (final item in rawList) {
        if (item is Map<String, dynamic>) {
          items.add(ScanSummaryItem.fromJson(item));
        } else if (item is Map) {
          items.add(ScanSummaryItem.fromJson(Map<String, dynamic>.from(item)));
        }
      }
    }

    return ScanHistoryPage(
      items: items,
      pageNumber: (json['number'] as num?)?.toInt() ?? 0,
      pageSize: (json['size'] as num?)?.toInt() ?? 20,
      totalElements: (json['totalElements'] as num?)?.toInt() ?? 0,
      totalPages: (json['totalPages'] as num?)?.toInt() ?? 0,
      isLast: json['last'] as bool? ?? true,
      isEmpty: json['empty'] as bool? ?? items.isEmpty,
    );
  }
}
