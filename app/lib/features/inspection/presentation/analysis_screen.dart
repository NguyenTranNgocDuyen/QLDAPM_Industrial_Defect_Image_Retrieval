import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../../../core/services/inspection_api_service.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import 'result_screen.dart';

class AnalysisScreen extends StatefulWidget {
  final String deviceName;
  final String deviceImei;
  final File imageFile;

  const AnalysisScreen({
    super.key,
    required this.deviceName,
    required this.deviceImei,
    required this.imageFile,
  });

  @override
  State<AnalysisScreen> createState() => _AnalysisScreenState();
}

class _AnalysisScreenState extends State<AnalysisScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _scanAnimController;
  int _currentPhaseIndex = 0;
  double _overallProgress = 0.04;
  String? _errorMessage;

  final List<String> _scanPhases = [
    'Tải ảnh và kiểm tra kết nối server',
    'Khử nhiễu quang học — Gaussian Filter (k=5)',
    'Resize và Normalize ảnh (224×224)',
    'Chạy DefectCNN — 3 Conv Blocks + Classifier',
    'Sigmoid → Phân loại Normal / Defective',
  ];

  @override
  void initState() {
    super.initState();
    _scanAnimController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);

    _runRealInference();
  }

  /// Gọi FastAPI thật; fallback sang mock nếu đang ở kDebugMode và server không có.
  Future<void> _runRealInference() async {
    // Kiểm tra server health
    _setPhase(0);
    await Future.delayed(const Duration(milliseconds: 300));

    final serverAlive = await InspectionApiService.isServerAlive();

    if (!serverAlive) {
      if (kDebugMode) {
        // Debug mode: dùng mock để test UI khi không có server
        debugPrint('[AnalysisScreen] Server offline — dùng mock data (kDebugMode)');
        await _runMockPipeline();
        return;
      }
      // Production: báo lỗi
      if (mounted) {
        setState(() => _errorMessage =
            'Không kết nối được model server.\n'
            'Hãy chạy:\n  uvicorn ui.local_api:app --port 8000');
        _showServerErrorSnackbar();
      }
      return;
    }

    // Tiến trình animation giả cho các bước preprocessing (UX)
    _setPhase(1);
    await Future.delayed(const Duration(milliseconds: 500));
    _setPhase(2);
    await Future.delayed(const Duration(milliseconds: 400));
    _setPhase(3);

    // Gọi API thật
    CnnResult result;
    try {
      result = await InspectionApiService.predict(widget.imageFile);
    } on InspectionApiException catch (e) {
      if (mounted) {
        setState(() => _errorMessage = e.message);
        _showServerErrorSnackbar(message: e.message);
      }
      return;
    } catch (e) {
      if (mounted) {
        setState(() => _errorMessage = 'Lỗi không xác định: $e');
        _showServerErrorSnackbar(message: 'Lỗi không xác định: $e');
      }
      return;
    }

    _setPhase(4);
    await Future.delayed(const Duration(milliseconds: 300));

    if (!mounted) return;
    setState(() => _overallProgress = 1.0);
    await Future.delayed(const Duration(milliseconds: 350));

    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => ResultScreen(
          deviceName: widget.deviceName,
          deviceImei: widget.deviceImei,
          cnnResult: result,
          imageFile: widget.imageFile,
        ),
      ),
    );
  }

  void _setPhase(int index) {
    if (!mounted) return;
    setState(() {
      _currentPhaseIndex = index;
      _overallProgress = (index + 1) / (_scanPhases.length + 1);
    });
  }

  /// Mock pipeline cho kDebugMode (test UI tanpa server).
  Future<void> _runMockPipeline() async {
    for (int i = 0; i < _scanPhases.length; i++) {
      _setPhase(i);
      await Future.delayed(const Duration(milliseconds: 600));
    }
    if (!mounted) return;
    setState(() => _overallProgress = 1.0);
    await Future.delayed(const Duration(milliseconds: 350));

    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => ResultScreen(
          deviceName: widget.deviceName,
          deviceImei: widget.deviceImei,
          // ignore: avoid_redundant_argument_values
          cnnResult: null, // null = mock mode
          imageFile: widget.imageFile,
        ),
      ),
    );
  }

  void _showServerErrorSnackbar({String? message}) {
    final msg = message ??
        'Không kết nối được model server. '
            'Hãy chạy: uvicorn ui.local_api:app --port 8000';
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg, style: const TextStyle(fontSize: 13)),
        backgroundColor: AppColors.defectCritical,
        duration: const Duration(seconds: 6),
        behavior: SnackBarBehavior.floating,
        action: SnackBarAction(
          label: 'OK',
          textColor: Colors.white,
          onPressed: () {},
        ),
      ),
    );
  }

  @override
  void dispose() {
    _scanAnimController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.darkCanvas,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('KHỐI PHÂN TÍCH QUANG HỌC',
                          style: AppTypography.labelCaps),
                      const SizedBox(height: 4),
                      Text(widget.deviceName,
                          style: AppTypography.titleMedium),
                    ],
                  ),
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 300),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: _errorMessage != null
                          ? AppColors.defectCritical.withOpacity(0.15)
                          : AppColors.amberMuted,
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(
                        color: _errorMessage != null
                            ? AppColors.defectCritical
                            : AppColors.amberAccent,
                        width: 1,
                      ),
                    ),
                    child: Text(
                      _errorMessage != null ? 'ERROR' : 'PROCESSING',
                      style: AppTypography.monoSmall.copyWith(
                        color: _errorMessage != null
                            ? AppColors.defectCritical
                            : AppColors.amberAccent,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Error banner
              if (_errorMessage != null)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: AppColors.defectCritical.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: AppColors.defectCritical),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.error_outline,
                              color: AppColors.defectCritical, size: 16),
                          SizedBox(width: 8),
                          Text('Lỗi kết nối server',
                              style: TextStyle(
                                  color: AppColors.defectCritical,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 13)),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        _errorMessage!,
                        style: const TextStyle(
                            color: Colors.white70, fontSize: 12),
                      ),
                    ],
                  ),
                ),

              // Vùng quét với image preview
              Expanded(
                flex: 3,
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: AppColors.darkSurface,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.darkBorder),
                  ),
                  child: Stack(
                    children: [
                      // Ảnh thật đang được phân tích (mờ nhẹ)
                      Positioned.fill(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: Opacity(
                            opacity: 0.35,
                            child: Image.file(
                              widget.imageFile,
                              fit: BoxFit.cover,
                            ),
                          ),
                        ),
                      ),

                      // Lưới tọa độ ma trận
                      Positioned.fill(
                        child: CustomPaint(
                          painter: _GridMatrixPainter(),
                        ),
                      ),

                      // Tia laser quét dọc (Scanline animation)
                      if (_errorMessage == null)
                        AnimatedBuilder(
                          animation: _scanAnimController,
                          builder: (context, child) {
                            return Positioned(
                              top: _scanAnimController.value * 280,
                              left: 0,
                              right: 0,
                              child: Container(
                                height: 2,
                                decoration: BoxDecoration(
                                  color: AppColors.amberAccent,
                                  boxShadow: [
                                    BoxShadow(
                                      color: AppColors.amberAccent
                                          .withOpacity(0.6),
                                      blurRadius: 6,
                                      spreadRadius: 1,
                                    ),
                                  ],
                                ),
                              ),
                            );
                          },
                        ),

                      // Thông số thời gian thực
                      Positioned(
                        bottom: 12,
                        left: 14,
                        right: 14,
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'SECTOR: #0${_currentPhaseIndex + 1} / CNN_SCAN',
                              style: AppTypography.monoSmall,
                            ),
                            Text(
                              '${(_overallProgress * 100).toInt()}% COMPLETE',
                              style: AppTypography.monoMetric.copyWith(
                                color: AppColors.amberAccent,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 24),

              // Tiến trình các bước
              Text('TIẾN TRÌNH THUẬT TOÁN CNN',
                  style: AppTypography.labelCaps),
              const SizedBox(height: 12),

              Expanded(
                flex: 2,
                child: ListView.separated(
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: _scanPhases.length,
                  separatorBuilder: (_, __) =>
                      const SizedBox(height: 8),
                  itemBuilder: (context, idx) {
                    final isDone = idx < _currentPhaseIndex;
                    final isRunning = idx == _currentPhaseIndex &&
                        _errorMessage == null;
                    final isError = idx == _currentPhaseIndex &&
                        _errorMessage != null;

                    return Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: isRunning
                            ? AppColors.darkSurfaceElevated
                            : AppColors.darkSurface,
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(
                          color: isError
                              ? AppColors.defectCritical
                              : isRunning
                                  ? AppColors.amberAccent
                                  : (isDone
                                      ? AppColors.statusPass
                                      : AppColors.darkBorderSubtle),
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            isError
                                ? Icons.error_outline
                                : isDone
                                    ? Icons.check_circle_outline
                                    : (isRunning
                                        ? Icons.radar
                                        : Icons.radio_button_unchecked),
                            size: 16,
                            color: isError
                                ? AppColors.defectCritical
                                : isDone
                                    ? AppColors.statusPass
                                    : (isRunning
                                        ? AppColors.amberAccent
                                        : AppColors.textMutedDark),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              _scanPhases[idx],
                              style: TextStyle(
                                fontSize: 12,
                                color: isError
                                    ? AppColors.defectCritical
                                    : isRunning
                                        ? Colors.white
                                        : (isDone
                                            ? AppColors.textSecondaryDark
                                            : AppColors.textMutedDark),
                              ),
                            ),
                          ),
                          if (isRunning)
                            const SizedBox(
                              width: 12,
                              height: 12,
                              child: CircularProgressIndicator(
                                strokeWidth: 1.5,
                                color: AppColors.amberAccent,
                              ),
                            ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _GridMatrixPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF242930)
      ..strokeWidth = 0.5;

    const step = 28.0;
    for (double x = 0; x < size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y < size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
