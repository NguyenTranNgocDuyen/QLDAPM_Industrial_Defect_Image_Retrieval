import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/defect_theme_ext.dart';
import '../../../core/widgets/severity_badge.dart';
import '../models/defect_item.dart';
import 'widgets/defect_overlay_painter.dart';
import 'history_screen.dart';

class ResultScreen extends StatefulWidget {
  final String deviceName;
  final String deviceImei;

  const ResultScreen({
    super.key,
    required this.deviceName,
    required this.deviceImei,
  });

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  bool _showOverlay = true;
  String? _selectedDefectId;

  // Dữ liệu mock kết quả AI thực tế
  late List<DefectItem> _defects;
  final CosmeticGrade _calculatedGrade = CosmeticGrade.gradeB;

  @override
  void initState() {
    super.initState();
    _defects = [
      const DefectItem(
        id: 'DEF-001',
        title: 'Xước dăm cạnh trên',
        locationDesc: 'Viền kim loại góc trên bên phải',
        lengthMm: 12.4,
        confidence: 0.91,
        severity: DefectSeverity.minor,
        relativeBox: Rect.fromLTWH(0.58, 0.12, 0.28, 0.08),
      ),
      const DefectItem(
        id: 'DEF-002',
        title: 'Cấn móp góc dưới',
        locationDesc: 'Cạnh dưới gần cổng sạc Type-C',
        lengthMm: 4.2,
        confidence: 0.88,
        severity: DefectSeverity.moderate,
        relativeBox: Rect.fromLTWH(0.24, 0.78, 0.22, 0.10),
      ),
      const DefectItem(
        id: 'DEF-003',
        title: 'Mòn phím âm lượng',
        locationDesc: 'Phím tăng âm lượng bên trái',
        lengthMm: 8.0,
        confidence: 0.94,
        severity: DefectSeverity.minor,
        relativeBox: Rect.fromLTWH(0.08, 0.32, 0.14, 0.12),
      ),
    ];
  }

  void _removeDefect(String id) {
    HapticFeedback.selectionClick();
    setState(() {
      _defects.removeWhere((item) => item.id == id);
      if (_selectedDefectId == id) _selectedDefectId = null;
    });
  }

  void _addManualDefect() {
    HapticFeedback.lightImpact();
    final newId = 'DEF-MAN-${_defects.length + 1}';
    setState(() {
      _defects.add(
        DefectItem(
          id: newId,
          title: 'Lỗi ghi nhận thủ công',
          locationDesc: 'QC đánh dấu thủ công qua chạm',
          lengthMm: 5.0,
          confidence: 1.0,
          severity: DefectSeverity.minor,
          relativeBox: const Rect.fromLTWH(0.40, 0.45, 0.20, 0.10),
          isUserVerified: true,
        ),
      );
      _selectedDefectId = newId;
    });
  }

  @override
  Widget build(BuildContext context) {
    final defectExt = Theme.of(context).extension<DefectThemeExtension>() ?? DefectThemeExtension.dark;

    return Scaffold(
      backgroundColor: AppColors.darkCanvas,
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.deviceName, style: AppTypography.titleMedium),
            Text('IMEI: ${widget.deviceImei}', style: AppTypography.monoSmall.copyWith(color: AppColors.amberAccent)),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Lịch sử kiểm định',
            icon: const Icon(Icons.history),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const HistoryScreen()),
              );
            },
          ),
          IconButton(
            tooltip: _showOverlay ? 'Ẩn lớp phủ lỗi' : 'Hiện lớp phủ lỗi',
            icon: Icon(
              _showOverlay ? Icons.layers : Icons.layers_clear,
              color: _showOverlay ? AppColors.amberAccent : Colors.white,
            ),
            onPressed: () => setState(() => _showOverlay = !_showOverlay),
          ),
        ],
      ),
      body: Column(
        children: [
          // 1. Phân vùng ảnh soi khuyết tật với pinch-to-zoom (InteractiveViewer)
          Expanded(
            flex: 5,
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.darkSurface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.darkBorder),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: InteractiveViewer(
                  minScale: 1.0,
                  maxScale: 4.5,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      // Giả lập ảnh chụp bề mặt thiết bị thực tế
                      Container(
                        color: const Color(0xFF191D22),
                        child: Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.smartphone, size: 84, color: AppColors.darkBorder),
                              const SizedBox(height: 8),
                              Text('HÌNH ẢNH GỐC ĐỘ PHÂN GIẢI CAO (4K)', style: AppTypography.monoSmall),
                            ],
                          ),
                        ),
                      ),

                      // Lớp phủ CustomPainter vẽ bounding boxes
                      if (_showOverlay)
                        Positioned.fill(
                          child: CustomPaint(
                            painter: DefectOverlayPainter(
                              defects: _defects,
                              selectedDefectId: _selectedDefectId,
                              showLabels: true,
                              defectColors: defectExt,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ),

          // 2. Tóm tắt phân hạng (Grading Header)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            color: AppColors.darkSurfaceElevated,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('KẾT LUẬN PHÂN LOẠI', style: AppTypography.labelCaps),
                    const SizedBox(height: 2),
                    Text(
                      _calculatedGrade.label,
                      style: AppTypography.titleLarge.copyWith(color: AppColors.amberAccent),
                    ),
                  ],
                ),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.darkSurface,
                    foregroundColor: Colors.white,
                    side: const BorderSide(color: AppColors.darkBorder),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                  ),
                  icon: const Icon(Icons.add, size: 16, color: AppColors.amberAccent),
                  label: const Text('Thêm lỗi thủ công', style: TextStyle(fontSize: 12)),
                  onPressed: _addManualDefect,
                ),
              ],
            ),
          ),

          // 3. Danh sách khuyết tật chi tiết (Tối ưu vuốt & chỉnh sửa)
          Expanded(
            flex: 4,
            child: _defects.isEmpty
                ? Center(
                    child: Text('Không phát hiện lỗi ngoại quan nào.', style: AppTypography.monoSmall),
                  )
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: _defects.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (context, idx) {
                      final item = _defects[idx];
                      final isSelected = item.id == _selectedDefectId;

                      return GestureDetector(
                        onTap: () {
                          HapticFeedback.selectionClick();
                          setState(() {
                            _selectedDefectId = isSelected ? null : item.id;
                          });
                        },
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: isSelected ? AppColors.darkSurfaceElevated : AppColors.darkSurface,
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(
                              color: isSelected ? AppColors.amberAccent : AppColors.darkBorder,
                              width: isSelected ? 1.5 : 1.0,
                            ),
                          ),
                          child: Row(
                            children: [
                              SeverityBadge(severity: item.severity),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(item.title, style: AppTypography.titleMedium.copyWith(fontSize: 13)),
                                    const SizedBox(height: 2),
                                    Text(item.locationDesc, style: AppTypography.monoSmall),
                                  ],
                                ),
                              ),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text('${item.lengthMm} mm', style: AppTypography.monoMetric),
                                  Text(
                                    '${(item.confidence * 100).toInt()}% conf',
                                    style: AppTypography.monoSmall.copyWith(color: AppColors.amberAccent),
                                  ),
                                ],
                              ),
                              const SizedBox(width: 8),
                              IconButton(
                                icon: const Icon(Icons.delete_outline, size: 18, color: AppColors.defectCritical),
                                tooltip: 'Xóa nhận diện sai',
                                onPressed: () => _removeDefect(item.id),
                              ),
                            ],
                          ),
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
