import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../models/defect_item.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  String _searchQuery = '';
  CosmeticGrade? _filterGrade;

  final List<InspectionRecord> _records = [
    InspectionRecord(
      id: 'REC-2026-0091',
      deviceName: 'Apple iPhone 13 Pro 128GB',
      imei: '356892110294812',
      inspectedAt: DateTime.now().subtract(const Duration(minutes: 25)),
      grade: CosmeticGrade.gradeB,
      defects: const [
        DefectItem(
          id: 'D1',
          title: 'Xước dăm',
          locationDesc: 'Cạnh trên',
          lengthMm: 12.4,
          confidence: 0.91,
          severity: DefectSeverity.minor,
          relativeBox: Rect.zero,
        )
      ],
      totalScannedSurfaces: 7,
    ),
    InspectionRecord(
      id: 'REC-2026-0090',
      deviceName: 'Bàn phím cơ Keychron K2 V2',
      imei: 'KC-994827104',
      inspectedAt: DateTime.now().subtract(const Duration(hours: 2)),
      grade: CosmeticGrade.gradeA,
      defects: const [],
      totalScannedSurfaces: 4,
    ),
    InspectionRecord(
      id: 'REC-2026-0089',
      deviceName: 'Dell XPS 13 Plus 9320',
      imei: 'SN-882941042',
      inspectedAt: DateTime.now().subtract(const Duration(hours: 5)),
      grade: CosmeticGrade.gradeC,
      defects: const [
        DefectItem(
          id: 'D2',
          title: 'Móp nắp lưng nhôm',
          locationDesc: 'Góc bản lề trái',
          lengthMm: 18.0,
          confidence: 0.95,
          severity: DefectSeverity.critical,
          relativeBox: Rect.zero,
        )
      ],
      totalScannedSurfaces: 6,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final filtered = _records.where((rec) {
      final matchesSearch = rec.imei.contains(_searchQuery) ||
          rec.deviceName.toLowerCase().contains(_searchQuery.toLowerCase());
      final matchesGrade = _filterGrade == null || rec.grade == _filterGrade;
      return matchesSearch && matchesGrade;
    }).toList();

    return Scaffold(
      backgroundColor: AppColors.darkCanvas,
      appBar: AppBar(
        title: Text('NHẬT KÝ KIỂM ĐỊNH (QC LOG)', style: AppTypography.titleMedium),
        actions: [
          IconButton(
            icon: const Icon(Icons.picture_as_pdf_outlined),
            tooltip: 'Xuất báo cáo PDF',
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Đang trích xuất báo cáo đo lường ISO sang định dạng PDF...'),
                ),
              );
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Thanh tìm kiếm IMEI & Filter nhanh
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                Expanded(
                  child: Container(
                    height: 42,
                    decoration: BoxDecoration(
                      color: AppColors.darkSurface,
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: AppColors.darkBorder),
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: TextField(
                      style: AppTypography.monoMetric,
                      decoration: InputDecoration(
                        border: InputBorder.none,
                        hintText: 'Tìm theo IMEI hoặc tên thiết bị...',
                        hintStyle: AppTypography.monoSmall,
                        icon: const Icon(Icons.search, size: 18, color: AppColors.textSecondaryDark),
                      ),
                      onChanged: (val) => setState(() => _searchQuery = val),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                DropdownButtonHideUnderline(
                  child: Container(
                    height: 42,
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                    decoration: BoxDecoration(
                      color: AppColors.darkSurface,
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: AppColors.darkBorder),
                    ),
                    child: DropdownButton<CosmeticGrade?>(
                      value: _filterGrade,
                      dropdownColor: AppColors.darkSurfaceElevated,
                      hint: Text('Tất cả hạng', style: AppTypography.monoSmall),
                      items: [
                        const DropdownMenuItem(
                          value: null,
                          child: Text('Tất cả', style: TextStyle(fontSize: 12)),
                        ),
                        ...CosmeticGrade.values.map(
                          (g) => DropdownMenuItem(
                            value: g,
                            child: Text(g.label, style: const TextStyle(fontSize: 12)),
                          ),
                        ),
                      ],
                      onChanged: (g) => setState(() => _filterGrade = g),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Danh sách biên bản
          Expanded(
            child: filtered.isEmpty
                ? Center(
                    child: Text('Không tìm thấy bản ghi phù hợp.', style: AppTypography.monoSmall),
                  )
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: filtered.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (context, idx) {
                      final rec = filtered[idx];
                      return Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: AppColors.darkSurface,
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: AppColors.darkBorder),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(rec.deviceName, style: AppTypography.titleMedium.copyWith(fontSize: 14)),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: AppColors.amberMuted,
                                    borderRadius: BorderRadius.circular(4),
                                    border: Border.all(color: AppColors.amberAccent),
                                  ),
                                  child: Text(
                                    rec.grade.label,
                                    style: AppTypography.monoSmall.copyWith(
                                      color: AppColors.amberAccent,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            Row(
                              children: [
                                Text('IMEI: ${rec.imei}', style: AppTypography.monoSmall),
                                const Spacer(),
                                Text(
                                  '${rec.defects.length} lỗi • ${rec.totalScannedSurfaces} mặt quét',
                                  style: AppTypography.monoSmall.copyWith(color: AppColors.textPrimaryDark),
                                ),
                              ],
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
