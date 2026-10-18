import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/services/inspection_api_service.dart';
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
  final CnnResult? cnnResult;   // null = mock / kDebugMode
  final File? imageFile;

  const ResultScreen({
    super.key,
    required this.deviceName,
    required this.deviceImei,
    this.cnnResult,
    this.imageFile,
  });

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen>
    with SingleTickerProviderStateMixin {
  bool _showOverlay = true;
  String? _selectedDefectId;

  late AnimationController _bannerAnimController;
  late Animation<double> _bannerScaleAnim;

  // Kết quả CNN thật (hoặc mock nếu server offline kDebugMode)
  late bool _isDefective;
  late double _confidence;
  late String _label;

  // TODO(TV2): Thay danh sách mock này bằng kết quả YOLO thật khi TV2 hoàn thành
  // TODO(TV2): DefectItem sẽ được tạo từ YOLO bounding box + class label
  late List<DefectItem> _defects;
  late CosmeticGrade _calculatedGrade;

  @override
  void initState() {
    super.initState();

    _bannerAnimController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _bannerScaleAnim = CurvedAnimation(
      parent: _bannerAnimController,
      curve: Curves.elasticOut,
    );
    _bannerAnimController.forward();

    // Dùng kết quả CNN thật nếu có, không thì dùng mock
    final result = widget.cnnResult;
    if (result != null) {
      _isDefective = result.isDefective;
      _confidence = result.confidence;
      _label = result.label;
    } else {
      // Mock data — kDebugMode hoặc khi server offline
      _isDefective = true;
      _confidence = 0.91;
      _label = 'defective';
    }

    // TODO(TV2): Khi YOLO hoàn thành, _defects sẽ đến từ API response của TV2
    // Nếu _isDefective == false, defects list là rỗng
    if (_isDefective) {
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
      _calculatedGrade = CosmeticGrade.gradeB;
    } else {
      _defects = [];
      _calculatedGrade = CosmeticGrade.gradeA;
    }
  }

  @override
  void dispose() {
    _bannerAnimController.dispose();
    super.dispose();
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
    final defectExt = Theme.of(context).extension<DefectThemeExtension>() ??
        DefectThemeExtension.dark;

    return Scaffold(
      backgroundColor: AppColors.darkCanvas,
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.deviceName, style: AppTypography.titleMedium),
            Text(
              'IMEI: ${widget.deviceImei}',
              style: AppTypography.monoSmall
                  .copyWith(color: AppColors.amberAccent),
            ),
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
            onPressed: () =>
                setState(() => _showOverlay = !_showOverlay),
          ),
        ],
      ),
      body: Column(
        children: [
          // 0. Banner kết quả CNN (thật từ model)
          ScaleTransition(
            scale: _bannerScaleAnim,
            child: _buildCnnBanner(),
          ),

          // 1. Phân vùng ảnh soi khuyết tật với pinch-to-zoom
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
                      // Ảnh thật nếu có, không thì placeholder
                      widget.imageFile != null
                          ? Image.file(
                              widget.imageFile!,
                              fit: BoxFit.cover,
                            )
                          : Container(
                              color: const Color(0xFF191D22),
                              child: Center(
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Icon(Icons.smartphone,
                                        size: 84,
                                        color: AppColors.darkBorder),
                                    const SizedBox(height: 8),
                                    Text(
                                      'HÌNH ẢNH GỐC ĐỘ PHÂN GIẢI CAO',
                                      style: AppTypography.monoSmall,
                                    ),
                                  ],
                                ),
                              ),
                            ),

                      // Lớp phủ CustomPainter vẽ bounding boxes
                      // TODO(TV2): Thay _defects mock bằng kết quả YOLO thật
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

          // 2. Tóm tắt phân hạng + timing metrics
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            color: AppColors.darkSurfaceElevated,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('KẾT LUẬN PHÂN LOẠI',
                            style: AppTypography.labelCaps),
                        const SizedBox(height: 2),
                        Text(
                          _calculatedGrade.label,
                          style: AppTypography.titleLarge
                              .copyWith(color: AppColors.amberAccent),
                        ),
                      ],
                    ),
                    ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.darkSurface,
                        foregroundColor: Colors.white,
                        side: const BorderSide(color: AppColors.darkBorder),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(4)),
                      ),
                      icon: const Icon(Icons.add,
                          size: 16, color: AppColors.amberAccent),
                      label: const Text('Thêm lỗi thủ công',
                          style: TextStyle(fontSize: 12)),
                      onPressed: _addManualDefect,
                    ),
                  ],
                ),
                // Timing metrics từ server (chỉ hiện nếu có kết quả thật)
                if (widget.cnnResult != null) ...[
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      _TimingChip(
                        label: 'Preprocess',
                        value: '${widget.cnnResult!.preprocessingMs.toStringAsFixed(1)} ms',
                      ),
                      const SizedBox(width: 8),
                      _TimingChip(
                        label: 'Inference',
                        value: '${widget.cnnResult!.inferenceMs.toStringAsFixed(1)} ms',
                      ),
                      const SizedBox(width: 8),
                      _TimingChip(
                        label: 'Conf',
                        value: '${(_confidence * 100).toStringAsFixed(1)}%',
                        highlight: true,
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),

          // 3. Danh sách khuyết tật chi tiết
          // TODO(TV2): Thay mock DefectItem bằng dữ liệu từ YOLO endpoint khi TV2 hoàn thành
          Expanded(
            flex: 4,
            child: _defects.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.check_circle_outline,
                          size: 48,
                          color: AppColors.statusPass,
                        ),
                        const SizedBox(height: 12),
                        Text(
                          'Không phát hiện lỗi ngoại quan.',
                          style: AppTypography.monoSmall,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'CNN confidence: ${(_confidence * 100).toStringAsFixed(1)}%',
                          style: AppTypography.monoSmall.copyWith(
                              color: AppColors.statusPass),
                        ),
                      ],
                    ),
                  )
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: _defects.length,
                    separatorBuilder: (_, __) =>
                        const SizedBox(height: 8),
                    itemBuilder: (context, idx) {
                      final item = _defects[idx];
                      final isSelected = item.id == _selectedDefectId;

                      return GestureDetector(
                        onTap: () {
                          HapticFeedback.selectionClick();
                          setState(() {
                            _selectedDefectId =
                                isSelected ? null : item.id;
                          });
                        },
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: isSelected
                                ? AppColors.darkSurfaceElevated
                                : AppColors.darkSurface,
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(
                              color: isSelected
                                  ? AppColors.amberAccent
                                  : AppColors.darkBorder,
                              width: isSelected ? 1.5 : 1.0,
                            ),
                          ),
                          child: Row(
                            children: [
                              SeverityBadge(severity: item.severity),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      item.title,
                                      style: AppTypography.titleMedium
                                          .copyWith(fontSize: 13),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(item.locationDesc,
                                        style: AppTypography.monoSmall),
                                  ],
                                ),
                              ),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text('${item.lengthMm} mm',
                                      style: AppTypography.monoMetric),
                                  Text(
                                    '${(item.confidence * 100).toInt()}% conf',
                                    style: AppTypography.monoSmall.copyWith(
                                        color: AppColors.amberAccent),
                                  ),
                                ],
                              ),
                              const SizedBox(width: 8),
                              IconButton(
                                icon: const Icon(Icons.delete_outline,
                                    size: 18,
                                    color: AppColors.defectCritical),
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

  Widget _buildCnnBanner() {
    if (_isDefective) {
      return Container(
        width: double.infinity,
        margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: AppColors.defectCritical.withOpacity(0.12),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: AppColors.defectCritical, width: 1.5),
        ),
        child: Row(
          children: [
            const Icon(Icons.warning_amber_rounded,
                color: AppColors.defectCritical, size: 22),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'PHÁT HIỆN LỖI NGOẠI QUAN',
                    style: AppTypography.labelCaps.copyWith(
                      color: AppColors.defectCritical,
                      letterSpacing: 1.2,
                    ),
                  ),
                  Text(
                    'CNN: $_label  •  Độ tin cậy: ${(_confidence * 100).toStringAsFixed(1)}%',
                    style: AppTypography.monoSmall.copyWith(
                      color: AppColors.defectCritical.withOpacity(0.8),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    } else {
      return Container(
        width: double.infinity,
        margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: AppColors.statusPass.withOpacity(0.10),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: AppColors.statusPass, width: 1.5),
        ),
        child: Row(
          children: [
            const Icon(Icons.check_circle_outline,
                color: AppColors.statusPass, size: 22),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'THIẾT BỊ KHÔNG LỖI',
                    style: AppTypography.labelCaps.copyWith(
                      color: AppColors.statusPass,
                      letterSpacing: 1.2,
                    ),
                  ),
                  Text(
                    'CNN: $_label  •  Độ tin cậy: ${(_confidence * 100).toStringAsFixed(1)}%',
                    style: AppTypography.monoSmall.copyWith(
                      color: AppColors.statusPass.withOpacity(0.8),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }
  }
}

/// Chip nhỏ hiển thị timing metrics từ server.
class _TimingChip extends StatelessWidget {
  final String label;
  final String value;
  final bool highlight;

  const _TimingChip({
    required this.label,
    required this.value,
    this.highlight = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: highlight
            ? AppColors.amberAccent.withOpacity(0.1)
            : AppColors.darkSurface,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(
          color: highlight ? AppColors.amberAccent : AppColors.darkBorderSubtle,
        ),
      ),
      child: RichText(
        text: TextSpan(
          children: [
            TextSpan(
              text: '$label: ',
              style: TextStyle(
                fontSize: 10,
                color: AppColors.textMutedDark,
                fontFamily: 'monospace',
              ),
            ),
            TextSpan(
              text: value,
              style: TextStyle(
                fontSize: 10,
                color: highlight ? AppColors.amberAccent : Colors.white,
                fontWeight: FontWeight.bold,
                fontFamily: 'monospace',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
