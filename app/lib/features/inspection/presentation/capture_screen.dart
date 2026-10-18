import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
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

class _CaptureScreenState extends State<CaptureScreen>
    with SingleTickerProviderStateMixin {
  DeviceProfile _currentProfile = DeviceProfile.smartphone;
  int _currentStepIndex = 0;
  bool _flashTorch = false;
  bool _gridVisible = true;
  File? _selectedImageFile;
  bool _isPickingImage = false;

  // Animation controller cho hiệu ứng preview ảnh
  late AnimationController _previewAnimController;
  late Animation<double> _previewFadeAnim;

  final CaptureCondition _condition = const CaptureCondition(
    stability: 0.94,
    lightingLux: 520,
    glareScore: 0.12,
    distanceCm: 18.5,
  );

  final Map<int, String> _capturedThumbnails = {};
  final List<InspectionStepType> _steps = InspectionStepType.values;
  final ImagePicker _imagePicker = ImagePicker();

  @override
  void initState() {
    super.initState();
    _previewAnimController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    _previewFadeAnim = CurvedAnimation(
      parent: _previewAnimController,
      curve: Curves.easeIn,
    );
  }

  @override
  void dispose() {
    _previewAnimController.dispose();
    super.dispose();
  }

  /// Mở gallery để chọn ảnh thật.
  Future<void> _onPickImageFromGallery() async {
    if (_isPickingImage) return;
    setState(() => _isPickingImage = true);

    try {
      final XFile? pickedFile = await _imagePicker.pickImage(
        source: ImageSource.gallery,
        imageQuality: 95,
        requestFullMetadata: false,
      );

      if (pickedFile == null) {
        // Người dùng huỷ chọn
        return;
      }

      final file = File(pickedFile.path);
      setState(() {
        _selectedImageFile = file;
        // Cập nhật thumbnail cho bước hiện tại
        _capturedThumbnails[_currentStepIndex] = pickedFile.path;
      });

      // Chạy animation fade-in cho preview
      _previewAnimController.reset();
      _previewAnimController.forward();

      HapticFeedback.mediumImpact();
    } on PlatformException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Không thể truy cập gallery: ${e.message}'),
            backgroundColor: AppColors.defectCritical,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isPickingImage = false);
    }
  }

  /// Chuyển sang màn hình phân tích với ảnh thật.
  void _onAnalyze() {
    if (_selectedImageFile == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Vui lòng chọn ảnh từ gallery trước.'),
          backgroundColor: AppColors.amberAccent,
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    HapticFeedback.mediumImpact();

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => AnalysisScreen(
          deviceName: widget.deviceName,
          deviceImei: widget.deviceImei,
          imageFile: _selectedImageFile!,
        ),
      ),
    );
  }

  // ignore: unused_element
  void _onTriggerShutterMock() {
    // TODO(TV2): Khi tích hợp camera thật, thay thế toàn bộ hàm này
    if (kDebugMode) {
      // Debug: chụp mock để test UI mà không cần ảnh thật
      setState(() {
        _capturedThumbnails[_currentStepIndex] =
            "mock_img_path_${_currentStepIndex}.jpg";
        if (_currentStepIndex < _steps.length - 1) {
          _currentStepIndex++;
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final activeStep = _steps[_currentStepIndex];
    final hasImage = _selectedImageFile != null;

    return Scaffold(
      backgroundColor: AppColors.darkCanvas,
      body: SafeArea(
        child: Stack(
          children: [
            // 1. Camera Viewport — hiển thị ảnh thật nếu đã chọn, không thì hiện placeholder
            Positioned.fill(
              child: hasImage
                  ? FadeTransition(
                      opacity: _previewFadeAnim,
                      child: Image.file(
                        _selectedImageFile!,
                        fit: BoxFit.cover,
                        width: double.infinity,
                        height: double.infinity,
                      ),
                    )
                  : Container(
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

            // Overlay tối nhẹ khi có ảnh để UI đọc được
            if (hasImage)
              Positioned.fill(
                child: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Colors.black.withOpacity(0.55),
                        Colors.transparent,
                        Colors.transparent,
                        Colors.black.withOpacity(0.7),
                      ],
                      stops: const [0.0, 0.25, 0.65, 1.0],
                    ),
                  ),
                ),
              ),

            // 2. Khung ngắm căn chỉnh quang học
            Positioned.fill(
              child: CaptureGuideOverlay(
                profile: _currentProfile,
                isReady: hasImage,
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
                        icon: const Icon(Icons.arrow_back,
                            size: 20, color: Colors.white),
                        onPressed: () => Navigator.maybePop(context),
                      ),
                      Expanded(
                        child: Padding(
                          padding:
                              const EdgeInsets.symmetric(horizontal: 12),
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
                              backgroundColor:
                                  AppColors.darkSurface.withOpacity(0.8),
                            ),
                            icon: Icon(
                              _flashTorch ? Icons.flash_on : Icons.flash_off,
                              size: 18,
                              color: _flashTorch
                                  ? AppColors.amberAccent
                                  : Colors.white,
                            ),
                            onPressed: () =>
                                setState(() => _flashTorch = !_flashTorch),
                          ),
                          const SizedBox(width: 6),
                          IconButton(
                            style: IconButton.styleFrom(
                              backgroundColor:
                                  AppColors.darkSurface.withOpacity(0.8),
                            ),
                            icon: Icon(
                              _gridVisible ? Icons.grid_on : Icons.grid_off,
                              size: 18,
                              color: _gridVisible
                                  ? AppColors.amberAccent
                                  : Colors.white,
                            ),
                            onPressed: () =>
                                setState(() => _gridVisible = !_gridVisible),
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
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.darkSurface.withOpacity(0.9),
                    border: Border.all(color: AppColors.darkBorder),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.compass_calibration_outlined,
                          size: 14, color: AppColors.amberAccent),
                      const SizedBox(width: 8),
                      Text(
                        'HƯỚNG CHỤP: ${activeStep.label.toUpperCase()}',
                        style: AppTypography.labelCaps
                            .copyWith(color: Colors.white),
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
                    top: BorderSide(
                        color: AppColors.darkBorderSubtle, width: 1),
                  ),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    StepThumbnailTray(
                      steps: _steps,
                      activeIndex: _currentStepIndex,
                      capturedThumbnails: _capturedThumbnails,
                      onStepSelected: (index) =>
                          setState(() => _currentStepIndex = index),
                    ),
                    const SizedBox(height: 18),
                    Padding(
                      padding:
                          const EdgeInsets.symmetric(horizontal: 24),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          // Dropdown loại thiết bị
                          DropdownButtonHideUnderline(
                            child: DropdownButton<DeviceProfile>(
                              value: _currentProfile,
                              dropdownColor: AppColors.darkSurfaceElevated,
                              icon: const Icon(Icons.arrow_drop_down,
                                  color: AppColors.textSecondaryDark),
                              items: const [
                                DropdownMenuItem(
                                  value: DeviceProfile.smartphone,
                                  child: Text('Smartphone',
                                      style: TextStyle(fontSize: 12)),
                                ),
                                DropdownMenuItem(
                                  value: DeviceProfile.keyboard,
                                  child: Text('Bàn phím',
                                      style: TextStyle(fontSize: 12)),
                                ),
                                DropdownMenuItem(
                                  value: DeviceProfile.laptop,
                                  child: Text('Laptop',
                                      style: TextStyle(fontSize: 12)),
                                ),
                              ],
                              onChanged: (val) {
                                if (val != null) {
                                  setState(() => _currentProfile = val);
                                }
                              },
                            ),
                          ),

                          // Nút chọn ảnh từ gallery (thay nút shutter mock)
                          GestureDetector(
                            onTap: _isPickingImage
                                ? null
                                : _onPickImageFromGallery,
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 150),
                              width: 76,
                              height: 76,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: hasImage
                                      ? AppColors.statusPass
                                      : AppColors.amberAccent,
                                  width: 3,
                                ),
                              ),
                              child: Center(
                                child: _isPickingImage
                                    ? const SizedBox(
                                        width: 28,
                                        height: 28,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2.5,
                                          color: AppColors.amberAccent,
                                        ),
                                      )
                                    : AnimatedContainer(
                                        duration:
                                            const Duration(milliseconds: 150),
                                        width: hasImage ? 60 : 56,
                                        height: hasImage ? 60 : 56,
                                        decoration: BoxDecoration(
                                          shape: BoxShape.circle,
                                          color: hasImage
                                              ? AppColors.statusPass
                                              : AppColors.amberAccent
                                                  .withOpacity(0.15),
                                          border: Border.all(
                                            color: hasImage
                                                ? AppColors.statusPass
                                                : AppColors.amberAccent,
                                            width: 1.5,
                                          ),
                                        ),
                                        child: Icon(
                                          hasImage
                                              ? Icons.check
                                              : Icons.photo_library_outlined,
                                          size: 26,
                                          color: hasImage
                                              ? Colors.white
                                              : AppColors.amberAccent,
                                        ),
                                      ),
                              ),
                            ),
                          ),

                          // Nút Phân tích (chỉ active khi đã có ảnh)
                          AnimatedOpacity(
                            opacity: hasImage ? 1.0 : 0.4,
                            duration: const Duration(milliseconds: 200),
                            child: IconButton(
                              iconSize: 26,
                              color: hasImage
                                  ? AppColors.amberAccent
                                  : AppColors.textSecondaryDark,
                              tooltip: hasImage
                                  ? 'Phân tích ảnh'
                                  : 'Chọn ảnh trước',
                              icon: const Icon(Icons.play_circle_fill_rounded),
                              onPressed: hasImage ? _onAnalyze : null,
                            ),
                          ),
                        ],
                      ),
                    ),

                    // Label hướng dẫn nhỏ bên dưới
                    const SizedBox(height: 6),
                    Text(
                      hasImage
                          ? 'Ảnh đã chọn — bấm ▶ để phân tích'
                          : 'Bấm  để chọn ảnh từ gallery',
                      style: TextStyle(
                        fontSize: 11,
                        color: AppColors.textMutedDark,
                        letterSpacing: 0.3,
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
