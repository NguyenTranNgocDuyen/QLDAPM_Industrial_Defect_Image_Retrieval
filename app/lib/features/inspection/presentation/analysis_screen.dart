import 'dart:async';
import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import 'result_screen.dart';

class AnalysisScreen extends StatefulWidget {
  final String deviceName;
  final String deviceImei;

  const AnalysisScreen({
    super.key,
    required this.deviceName,
    required this.deviceImei,
  });

  @override
  State<AnalysisScreen> createState() => _AnalysisScreenState();
}

class _AnalysisScreenState extends State<AnalysisScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _scanAnimController;
  int _currentPhaseIndex = 0;
  double _overallProgress = 0.08;

  final List<String> _scanPhases = [
    'Khử nhiễu quang học & cân bằng phơi sáng',
    'Phân đoạn viền máy & bề mặt kính (Segmentation)',
    'Quét micro-crack & xước dăm bằng Kernel tích chập',
    'Đo lường kích thước & phân loại cấp độ lỗi',
    'Tổng hợp ma trận phân hạng ngoại quan'
  ];

  Timer? _progressTimer;

  @override
  void initState() {
    super.initState();
    _scanAnimController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);

    _startSimulatedPipeline();
  }

  void _startSimulatedPipeline() {
    _progressTimer = Timer.periodic(const Duration(milliseconds: 600), (timer) {
      if (!mounted) return;
      setState(() {
        _overallProgress += 0.22;
        if (_overallProgress >= 1.0) {
          _overallProgress = 1.0;
          timer.cancel();
          Future.delayed(const Duration(milliseconds: 400), () {
            if (!mounted) return;
            Navigator.of(context).pushReplacement(
              MaterialPageRoute(
                builder: (_) => ResultScreen(
                  deviceName: widget.deviceName,
                  deviceImei: widget.deviceImei,
                ),
              ),
            );
          });
        } else {
          _currentPhaseIndex = (_overallProgress * (_scanPhases.length - 1)).toInt();
        }
      });
    });
  }

  @override
  void dispose() {
    _progressTimer?.cancel();
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
                      Text('KHỐI PHÂN TÍCH QUANG HỌC', style: AppTypography.labelCaps),
                      const SizedBox(height: 4),
                      Text(widget.deviceName, style: AppTypography.titleMedium),
                    ],
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.amberMuted,
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: AppColors.amberAccent, width: 1),
                    ),
                    child: Text(
                      'PROCESSING',
                      style: AppTypography.monoSmall.copyWith(
                        color: AppColors.amberAccent,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Vùng quét giả lập quét theo từng khu vực (Sector-by-sector scanner)
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
                      // Lưới tọa độ ma trận
                      Positioned.fill(
                        child: CustomPaint(
                          painter: _GridMatrixPainter(),
                        ),
                      ),

                      // Tia laser quét dọc (Scanline animation)
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
                                    color: AppColors.amberAccent.withOpacity(0.6),
                                    blurRadius: 6,
                                    spreadRadius: 1,
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),

                      // Thông số thời gian thực đè lên màn hình quét
                      Positioned(
                        bottom: 12,
                        left: 14,
                        right: 14,
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'SECTOR: #0${_currentPhaseIndex + 1} / REGION_SCAN',
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
              Text('TIẾN TRÌNH THỰC THI THUẬT TOÁN', style: AppTypography.labelCaps),
              const SizedBox(height: 12),

              Expanded(
                flex: 2,
                child: ListView.separated(
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: _scanPhases.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, idx) {
                    final isDone = idx < _currentPhaseIndex;
                    final isRunning = idx == _currentPhaseIndex;

                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: isRunning
                            ? AppColors.darkSurfaceElevated
                            : AppColors.darkSurface,
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(
                          color: isRunning
                              ? AppColors.amberAccent
                              : (isDone ? AppColors.statusPass : AppColors.darkBorderSubtle),
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            isDone
                                ? Icons.check_circle_outline
                                : (isRunning ? Icons.radar : Icons.radio_button_unchecked),
                            size: 16,
                            color: isDone
                                ? AppColors.statusPass
                                : (isRunning ? AppColors.amberAccent : AppColors.textMutedDark),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              _scanPhases[idx],
                              style: TextStyle(
                                fontSize: 12,
                                color: isRunning
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
