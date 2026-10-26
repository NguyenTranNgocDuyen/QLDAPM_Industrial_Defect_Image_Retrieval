import 'dart:async';
import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../data/damage_api.dart';
import '../models/capture_condition.dart';
import '../models/scan_history_model.dart';
import 'result_screen.dart';

class HistoryScreen extends StatefulWidget {
  final DamageApi? damageApi;

  const HistoryScreen({super.key, this.damageApi});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  late final DamageApi _api;
  final List<ScanDateGroup> _dateGroups = [];
  final Map<String, List<InspectionSessionItem>> _sessionsByDate = {};
  final Set<String> _expandedDates = {};
  final Set<String> _loadingDates = {};

  bool _initialLoading = true;
  String? _errorMessage;
  int _refreshCounter = 0;

  @override
  void initState() {
    super.initState();
    _api = widget.damageApi ?? DamageApi();
    unawaited(_loadDates());
  }

  @override
  void dispose() {
    if (widget.damageApi == null) {
      _api.close();
    }
    super.dispose();
  }

  Future<void> _loadDates() async {
    setState(() {
      _initialLoading = true;
      _errorMessage = null;
    });
    final thisCounter = ++_refreshCounter;
    try {
      final dates = await _api.getScanDates();
      if (!mounted || thisCounter != _refreshCounter) return;
      setState(() {
        _dateGroups.clear();
        _dateGroups.addAll(dates);
        _initialLoading = false;
      });

      // Auto expand the most recent date if available
      if (_dateGroups.isNotEmpty) {
        unawaited(_toggleDateExpand(_dateGroups.first.dateString));
      }
    } catch (e) {
      if (!mounted || thisCounter != _refreshCounter) return;
      setState(() {
        _errorMessage = e.toString();
        _initialLoading = false;
      });
    }
  }

  Future<void> _onRefresh() async {
    _sessionsByDate.clear();
    _expandedDates.clear();
    _loadingDates.clear();
    await _loadDates();
  }

  Future<void> _toggleDateExpand(String dateString) async {
    if (_expandedDates.contains(dateString)) {
      setState(() => _expandedDates.remove(dateString));
      return;
    }

    setState(() => _expandedDates.add(dateString));

    if (!_sessionsByDate.containsKey(dateString)) {
      setState(() => _loadingDates.add(dateString));
      try {
        final sessions = await _api.getInspectionSessions(date: dateString);
        if (!mounted) return;
        setState(() {
          _sessionsByDate[dateString] = sessions;
          _loadingDates.remove(dateString);
        });
      } catch (e) {
        if (!mounted) return;
        setState(() => _loadingDates.remove(dateString));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Không thể tải các lượt quét ngày $dateString: $e'),
            backgroundColor: AppColors.statusFail,
          ),
        );
      }
    }
  }

  Future<void> _openSessionDetail(InspectionSessionItem session) async {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(
        child: CircularProgressIndicator(),
      ),
    );
    try {
      final futures = <Future<void>>[];
      Map<String, dynamic>? frontDetail;
      Map<String, dynamic>? backDetail;

      if (session.frontScan != null) {
        futures.add(
          _api.getScanDetail(session.frontScan!.scanId).then((res) {
            frontDetail = res;
          }),
        );
      }
      if (session.backScan != null) {
        futures.add(
          _api.getScanDetail(session.backScan!.scanId).then((res) {
            backDetail = res;
          }),
        );
      }

      await Future.wait(futures);
      if (!mounted) return;
      Navigator.of(context).pop(); // dismiss loading dialog

      final resultsMap = <InspectionStepType, Map<String, dynamic>>{};
      if (frontDetail != null) {
        resultsMap[InspectionStepType.front] = frontDetail!;
      }
      if (backDetail != null) {
        resultsMap[InspectionStepType.back] = backDetail!;
      }

      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => ResultScreen(
            deviceName: session.deviceInfo?.isNotEmpty == true
                ? session.deviceInfo!
                : 'Lịch sử · ${session.shortSessionId}',
            deviceImei: '',
            results: resultsMap,
            singleScanResult: resultsMap.length == 1 ? resultsMap.values.first : null,
            damageApi: _api,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      Navigator.of(context).pop(); // dismiss loading dialog
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Không thể tải chi tiết phiên quét: $e'),
          backgroundColor: AppColors.statusFail,
        ),
      );
    }
  }

  String _formatTime(DateTime? dt) {
    if (dt == null) return '';
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }

  Widget _buildSessionSeverityBadge(InspectionSessionItem session) {
    final sev = session.overallSeverity;
    final needsReview = session.needsReview == true;

    if (sev != null) {
      final level = {
        'minor': 'Nhẹ',
        'moderate': 'Vừa',
        'severe': 'Nặng',
      }[sev] ?? sev;

      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: AppColors.amberMuted,
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: AppColors.amberAccent),
        ),
        child: Text(
          '$level · Ước tính${needsReview ? ' · Cần kiểm tra' : ''}',
          style: AppTypography.monoSmall.copyWith(
            color: AppColors.amberAccent,
            fontWeight: FontWeight.bold,
          ),
        ),
      );
    }

    if (session.hasDefect == false) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: AppColors.statusPass.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: AppColors.statusPass),
        ),
        child: Text(
          'Chưa đạt ngưỡng báo ứng viên',
          style: AppTypography.monoSmall.copyWith(
            color: AppColors.statusPass,
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.darkSurfaceElevated,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: AppColors.darkBorder),
      ),
      child: Text(
        needsReview ? 'Cần kiểm tra' : 'Đã phân tích',
        style: AppTypography.monoSmall.copyWith(
          color: AppColors.textSecondaryDark,
        ),
      ),
    );
  }

  Widget _buildMiniSurfaceBadge(ScanSummaryItem scan) {
    final sev = scan.estimatedSeverity;
    if (sev != null) {
      final level = {
        'minor': 'Nhẹ',
        'moderate': 'Vừa',
        'severe': 'Nặng',
      }[sev] ?? sev;
      return Text(
        '$level · Ước tính',
        style: const TextStyle(fontSize: 11, color: AppColors.amberAccent, fontWeight: FontWeight.bold),
      );
    }
    return Text(
      scan.status == 'no_detected_damage' ? 'Chưa thấy ứng viên' : 'Đã quét',
      style: const TextStyle(fontSize: 11, color: AppColors.textSecondaryDark),
    );
  }

  Widget _buildSurfaceThumbnail(String label, ScanSummaryItem scan) {
    final thumbUrl = scan.displayImageUrl ?? scan.sourceImageUrl;
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: AppColors.darkSurfaceElevated,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.darkBorder),
      ),
      child: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: Container(
              width: 48,
              height: 48,
              color: AppColors.darkCanvas,
              child: thumbUrl != null
                  ? Image.network(
                      DamageApi.assetUrl(thumbUrl),
                      fit: BoxFit.cover,
                      errorBuilder: (_, _, _) => const Center(
                        child: Icon(Icons.broken_image, size: 20, color: AppColors.textMutedDark),
                      ),
                    )
                  : const Center(
                      child: Icon(Icons.image_not_supported_outlined, size: 20, color: AppColors.textMutedDark),
                    ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                ),
                const SizedBox(height: 3),
                _buildMiniSurfaceBadge(scan),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSessionCard(InspectionSessionItem session) {
    final front = session.frontScan;
    final back = session.backScan;
    final timeStr = _formatTime(session.createdAt);
    final title = session.deviceInfo?.isNotEmpty == true
        ? session.deviceInfo!
        : 'Quét #${session.shortSessionId}';

    return InkWell(
      onTap: () => _openSessionDetail(session),
      borderRadius: BorderRadius.circular(10),
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.darkSurface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppColors.darkBorder),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Row(
                    children: [
                      const Icon(Icons.phone_android, size: 18, color: AppColors.amberAccent),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          title,
                          style: AppTypography.titleMedium.copyWith(fontSize: 14),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
                Text(
                  timeStr,
                  style: AppTypography.monoSmall.copyWith(
                    color: AppColors.textSecondaryDark,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                if (front != null)
                  Expanded(child: _buildSurfaceThumbnail('Mặt trước', front))
                else
                  const Expanded(child: SizedBox()),
                const SizedBox(width: 8),
                if (back != null)
                  Expanded(child: _buildSurfaceThumbnail('Mặt sau', back))
                else
                  const Expanded(child: SizedBox()),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _buildSessionSeverityBadge(session),
                Row(
                  children: [
                    Text(
                      front != null && back != null ? 'Xem cả 2 mặt' : 'Xem chi tiết',
                      style: AppTypography.bodyMedium.copyWith(
                        color: AppColors.amberAccent,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const Icon(
                      Icons.chevron_right,
                      color: AppColors.amberAccent,
                      size: 18,
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDateSection(ScanDateGroup group) {
    final dateKey = group.dateString;
    final isExpanded = _expandedDates.contains(dateKey);
    final isLoading = _loadingDates.contains(dateKey);
    final sessions = _sessionsByDate[dateKey];

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppColors.darkSurfaceElevated,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: isExpanded ? AppColors.amberAccent.withValues(alpha: 0.5) : AppColors.darkBorder,
        ),
      ),
      child: Column(
        children: [
          InkWell(
            onTap: () => _toggleDateExpand(dateKey),
            borderRadius: BorderRadius.circular(10),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.amberMuted,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.calendar_today, size: 20, color: AppColors.amberAccent),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          group.displayTitle,
                          style: AppTypography.titleMedium.copyWith(fontSize: 15, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          '${group.sessionCount} lượt kiểm tra · ${group.scanCount} ảnh',
                          style: AppTypography.bodyMedium.copyWith(color: AppColors.textSecondaryDark, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                  if (group.hasDefectCount > 0)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      margin: const EdgeInsets.only(right: 8),
                      decoration: BoxDecoration(
                        color: AppColors.amberMuted,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppColors.amberAccent.withValues(alpha: 0.5)),
                      ),
                      child: Text(
                        '${group.hasDefectCount} có ứng viên',
                        style: AppTypography.monoSmall.copyWith(
                          color: AppColors.amberAccent,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  Icon(
                    isExpanded ? Icons.expand_less : Icons.expand_more,
                    color: AppColors.textSecondaryDark,
                  ),
                ],
              ),
            ),
          ),
          if (isExpanded) ...[
            const Divider(height: 1, color: AppColors.darkBorder),
            Padding(
              padding: const EdgeInsets.all(12),
              child: isLoading
                  ? const Padding(
                      padding: EdgeInsets.symmetric(vertical: 20),
                      child: Center(
                        child: Column(
                          children: [
                            SizedBox(
                              width: 24,
                              height: 24,
                              child: CircularProgressIndicator(strokeWidth: 2.5),
                            ),
                            SizedBox(height: 10),
                            Text('Đang tải các lượt quét...', style: TextStyle(fontSize: 13, color: AppColors.textSecondaryDark)),
                          ],
                        ),
                      ),
                    )
                  : (sessions == null || sessions.isEmpty)
                      ? const Padding(
                          padding: EdgeInsets.symmetric(vertical: 16),
                          child: Center(
                            child: Text('Không có dữ liệu lượt quét trong ngày này.', style: TextStyle(color: AppColors.textMutedDark)),
                          ),
                        )
                      : Column(
                          children: sessions.map((s) => _buildSessionCard(s)).toList(),
                        ),
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.darkCanvas,
      appBar: AppBar(
        title: Text('Lịch sử quét', style: AppTypography.titleMedium),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Làm mới',
            onPressed: _initialLoading ? null : _loadDates,
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_initialLoading) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Đang tải danh sách ngày...'),
          ],
        ),
      );
    }

    if (_errorMessage != null && _dateGroups.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, size: 54, color: AppColors.statusFail),
              const SizedBox(height: 16),
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: AppTypography.bodyMedium,
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: _loadDates,
                icon: const Icon(Icons.refresh),
                label: const Text('Thử lại'),
              ),
            ],
          ),
        ),
      );
    }

    if (_dateGroups.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.history,
                size: 54,
                color: AppColors.textSecondaryDark,
              ),
              const SizedBox(height: 16),
              const Text(
                'Chưa có lượt quét nào trên máy chủ.',
                style: TextStyle(fontSize: 16),
              ),
              const SizedBox(height: 8),
              const Text(
                'Hãy thực hiện chụp hoặc chọn ảnh để kiểm tra thiết bị.',
                style: TextStyle(color: AppColors.textSecondaryDark),
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: _loadDates,
                icon: const Icon(Icons.refresh),
                label: const Text('Làm mới'),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _onRefresh,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _dateGroups.length,
        itemBuilder: (context, idx) {
          final group = _dateGroups[idx];
          return _buildDateSection(group);
        },
      ),
    );
  }
}
