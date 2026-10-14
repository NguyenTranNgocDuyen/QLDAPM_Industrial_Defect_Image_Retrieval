import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/quality_indicator.dart';
import '../models/capture_condition.dart';
import 'widgets/capture_guide_overlay.dart';
import 'widgets/thumbnail_step_tray.dart';
import 'analysis_screen.dart';

class CaptureScreen extends StatefulWidget {
  final String deviceImei;
  final String deviceName;

  const CaptureScreen({
    super.key,
    this.deviceImei = "356892110294812",
    this.deviceName = "Apple iPhone 13 Pro 128GB",
  });

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  DeviceProfile _currentProfile = DeviceProfile.smartphone;
  int _currentStepIndex = 0;
  bool _flashTorch = false;
  bool _gridVisible = true;

  final CaptureCondition _condition = const CaptureCondition(
    stability: 0.94,
    lightingLux: 520,
    glareScore: 0.12,
    distanceCm: 18.5,
  );

  final Map<int, String> _capturedThumbnails = {};
  final List<InspectionStepType> _steps = InspectionStepType.values;

  void _onTriggerShutter() {
    if (!_condition.isReadyToCapture) {
      HapticFeedback.heavyImpact();
      return;
    }

    HapticFeedback.mediumImpact();

    setState(() {
      _capturedThumbnails[_currentStepIndex] = "mock_img_path_${_currentStepIndex}.jpg";
      if (_currentStepIndex < _steps.length - 1) {
        _currentStepIndex++;
      } else {
        // Đã chụp đủ góc -> Chuyển sang màn hình phân tích tiến trình
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => AnalysisScreen(
              deviceName: widget.deviceName,
              deviceImei: widget.deviceImei,
            ),
          ),
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final activeStep = _steps[_currentStepIndex];
    final isReady = _condition.isReadyToCapture;

    return Scaffold(
      backgroundColor: AppColors.darkCanvas,
      body: SafeArea(
        child: Stack(
          children: [
            // 1. Camera Viewport
            Positioned.fill(
              child: Container(
                color: const Color(0xFF14171B),
                child: Center(
                  child: Opacity(
                    opacity: 0.15,
                    child: Icon(
                      Icons.camera_alt_outlined,
                      size: 120,
                      color: AppColors.textSecondaryDark,
                    ),
                  ),
                ),
              ),
            ),

            // 2. Khung ngắm căn chỉnh quang học
            Positioned.fill(
              child: CaptureGuideOverlay(
                profile: _currentProfile,
                isReady: isReady,
              ),
            ),

            // 3. Header điều khiển trên cùng
            Positioned(
              top: 12,
              left: 16,
              right: 16,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      IconButton(
                        style: IconButton.styleFrom(
                          backgroundColor: AppColors.darkSurface.withOpacity(0.8),
                          minimumSize: const Size(44, 44),
                        ),
                        icon: const Icon(Icons.arrow_back, size: 20, color: Colors.white),
                        onPressed: () => Navigator.maybePop(context),
                      ),
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                widget.deviceName,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: AppTypography.titleMedium,
                              ),
                              Text(
                                'SN/IMEI: ${widget.deviceImei}',
                                style: AppTypography.monoSmall.copyWith(
                                  color: AppColors.amberAccent,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      Row(
                        children: [
                          IconButton(
                            style: IconButton.styleFrom(
                              backgroundColor: AppColors.darkSurface.withOpacity(0.8),
                            ),
                            icon: Icon(
                              _flashTorch ? Icons.flash_on : Icons.flash_off,
                              size: 18,
                              color: _flashTorch ? AppColors.amberAccent : Colors.white,
                            ),
                            onPressed: () => setState(() => _flashTorch = !_flashTorch),
                          ),
                          const SizedBox(width: 6),
                          IconButton(
                            style: IconButton.styleFrom(
                              backgroundColor: AppColors.darkSurface.withOpacity(0.8),
                            ),
                            icon: Icon(
                              _gridVisible ? Icons.grid_on : Icons.grid_off,
                              size: 18,
                              color: _gridVisible ? AppColors.amberAccent : Colors.white,
                            ),
                            onPressed: () => setState(() => _gridVisible = !_gridVisible),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  QualityIndicatorHUD(condition: _condition),
                ],
              ),
            ),

            // 4. Chỉ dẫn góc chụp hiện tại
            Positioned(
              top: 110,
              left: 16,
              right: 16,
              child: Align(
                alignment: Alignment.center,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.darkSurface.withOpacity(0.9),
                    border: Border.all(color: AppColors.darkBorder),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.compass_calibration_outlined, size: 14, color: AppColors.amberAccent),
                      const SizedBox(width: 8),
                      Text(
                        'HƯỚNG CHỤP: ${activeStep.label.toUpperCase()}',
                        style: AppTypography.labelCaps.copyWith(color: Colors.white),
                      ),
                    ],
                  ),
                ),
              ),
            ),

            // 5. Khu vực thao tác vùng ngón cái (Thumb Zone)
            Positioned(
              bottom: 0,
              left: 0,
              right: 0,
              child: Container(
                padding: const EdgeInsets.only(top: 14, bottom: 20),
                decoration: BoxDecoration(
                  color: AppColors.darkCanvas.withOpacity(0.95),
                  border: const Border(
                    top: BorderSide(color: AppColors.darkBorderSubtle, width: 1),
                  ),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    StepThumbnailTray(
                      steps: _steps,
                      activeIndex: _currentStepIndex,
                      capturedThumbnails: _capturedThumbnails,
                      onStepSelected: (index) => setState(() => _currentStepIndex = index),
                    ),
                    const SizedBox(height: 18),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          DropdownButtonHideUnderline(
                            child: DropdownButton<DeviceProfile>(
                              value: _currentProfile,
                              dropdownColor: AppColors.darkSurfaceElevated,
                              icon: const Icon(Icons.arrow_drop_down, color: AppColors.textSecondaryDark),
                              items: const [
                                DropdownMenuItem(
                                  value: DeviceProfile.smartphone,
                                  child: Text('Smartphone', style: TextStyle(fontSize: 12)),
                                ),
                                DropdownMenuItem(
                                  value: DeviceProfile.keyboard,
                                  child: Text('Bàn phím', style: TextStyle(fontSize: 12)),
                                ),
                                DropdownMenuItem(
                                  value: DeviceProfile.laptop,
                                  child: Text('Laptop', style: TextStyle(fontSize: 12)),
                                ),
                              ],
                              onChanged: (val) {
                                if (val != null) setState(() => _currentProfile = val);
                              },
                            ),
                          ),
                          GestureDetector(
                            onTap: _onTriggerShutter,
                            child: Container(
                              width: 76,
                              height: 76,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: isReady ? AppColors.amberAccent : AppColors.darkBorder,
                                  width: 3,
                                ),
                              ),
                              child: Center(
                                child: AnimatedContainer(
                                  duration: const Duration(milliseconds: 150),
                                  width: isReady ? 60 : 54,
                                  height: isReady ? 60 : 54,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: isReady
                                        ? AppColors.amberAccent
                                        : AppColors.darkBorder,
                                  ),
                                  child: isReady
                                      ? null
                                      : const Icon(
                                          Icons.lock_outline,
                                          size: 22,
                                          color: AppColors.textMutedDark,
                                        ),
                                ),
                              ),
                            ),
                          ),
                          IconButton(
                            iconSize: 26,
                            color: AppColors.textSecondaryDark,
                            tooltip: 'Chụp lại góc này',
                            icon: const Icon(Icons.replay),
                            onPressed: () {
                              setState(() {
                                _capturedThumbnails.remove(_currentStepIndex);
                              });
                              HapticFeedback.selectionClick();
                            },
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
