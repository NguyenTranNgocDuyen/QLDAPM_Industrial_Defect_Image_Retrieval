import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../data/damage_api.dart';
import '../models/capture_condition.dart';
import 'widgets/capture_guide_overlay.dart';
import 'widgets/thumbnail_step_tray.dart';
import 'analysis_screen.dart';
import 'history_screen.dart';
import 'photo_review_screen.dart';

class CaptureScreen extends StatefulWidget {
  final String deviceImei;
  final String deviceName;
  final ImagePicker? imagePicker;

  const CaptureScreen({
    super.key,
    this.deviceImei = "356892110294812",
    this.deviceName = "Apple iPhone 13 Pro 128GB",
    this.imagePicker,
  });

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen>
    with WidgetsBindingObserver {
  late final ImagePicker _picker;
  DeviceProfile _currentProfile = DeviceProfile.smartphone;
  int _currentStepIndex = 0;
  bool _flashTorch = false;
  bool _gridVisible = true;

  CameraController? _camera;
  Future<void> _cameraQueue = Future<void>.value();
  bool _cameraWanted = true;
  bool _cameraLoading = true;
  bool _isCapturing = false;
  bool _changingFlash = false;
  bool _analysisOpen = false;
  bool _reviewOpen = false;
  bool _isPickingGallery = false;
  bool _historyOpen = false;
  bool _isSubmitting = false;
  String? _cameraError;

  final Map<int, String> _capturedThumbnails = {};
  final Map<int, Uint8List> _thumbnailBytes = {};
  final Map<int, bool> _isGalleryPhoto = {};
  static const List<InspectionStepType> _steps = [
    InspectionStepType.front,
    InspectionStepType.back,
  ];

  bool get _cameraReady =>
      _camera?.value.isInitialized == true &&
      _camera?.value.hasError == false &&
      _cameraError == null &&
      _cameraWanted &&
      !_cameraLoading;

  bool get _hasBothPhotos => _steps.asMap().keys.every(
    (index) => _capturedThumbnails.containsKey(index),
  );

  bool get _isBusy =>
      _isCapturing ||
      _isSubmitting ||
      _reviewOpen ||
      _isPickingGallery ||
      _historyOpen;

  @override
  void initState() {
    super.initState();
    _picker = widget.imagePicker ?? ImagePicker();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_syncCamera());
    unawaited(_checkLostData());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _cameraWanted =
        state == AppLifecycleState.resumed &&
        !_analysisOpen &&
        !_reviewOpen &&
        !_isPickingGallery &&
        !_historyOpen;
    unawaited(_syncCamera());
  }

  Future<void> _checkLostData() async {
    try {
      final response = await _picker.retrieveLostData();
      if (response.isEmpty || response.file == null || !mounted) return;
      final file = response.file!;
      final length = await file.length();
      if (length > 25 * 1024 * 1024) return;
      final bytes = await file.readAsBytes();
      try {
        DamageApi.detectMimeAndFilename(file.path, bytes);
      } catch (_) {
        return;
      }
      final index = _currentStepIndex;
      setState(() {
        _capturedThumbnails[index] = file.path;
        _thumbnailBytes[index] = bytes;
        _isGalleryPhoto[index] = true;
      });
      await _reviewCapturedPhoto(index);
    } catch (error) {
      debugPrint('retrieveLostData error: $error');
    }
  }

  // Serialize camera operations so returning from background never opens
  // a second camera while the previous session is still being released.
  Future<void> _syncCamera() {
    _cameraQueue = _cameraQueue.then((_) => _updateCamera());
    return _cameraQueue;
  }

  Future<void> _releaseCamera() async {
    final camera = _camera;
    _camera = null;
    _flashTorch = false;
    camera?.removeListener(_onCameraChanged);
    if (mounted) setState(() {});
    try {
      await camera?.dispose();
    } catch (error) {
      debugPrint('Camera dispose: $error');
    }
  }

  Future<void> _updateCamera() async {
    if (!mounted || !_cameraWanted) {
      await _releaseCamera();
      return;
    }
    if (_cameraReady) return;

    await _releaseCamera();
    if (!mounted || !_cameraWanted) return;
    setState(() {
      _cameraLoading = true;
      _cameraError = null;
    });

    CameraController? camera;
    try {
      final cameras = await availableCameras();
      if (!mounted || !_cameraWanted) return;
      if (cameras.isEmpty) {
        throw CameraException(
          'NoCamera',
          'Không tìm thấy camera trên thiết bị.',
        );
      }
      final description = cameras.firstWhere(
        (cam) => cam.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      camera = CameraController(
        description,
        ResolutionPreset.high,
        enableAudio: false,
      );
      await camera.initialize();
      if (!mounted || !_cameraWanted) {
        await camera.dispose();
        return;
      }
      try {
        await camera.setFlashMode(FlashMode.off);
      } on CameraException catch (_) {}
      if (!mounted || !_cameraWanted) {
        await camera.dispose();
        return;
      }
      _camera = camera;
      camera.addListener(_onCameraChanged);
    } catch (error) {
      await camera?.dispose();
      if (mounted && _cameraWanted) {
        _cameraError = _cameraErrorMessage(error);
      }
    } finally {
      if (mounted) setState(() => _cameraLoading = false);
    }
  }

  String _cameraErrorMessage(Object error) {
    if (error is CameraException) {
      switch (error.code) {
        case 'CameraAccessDenied':
        case 'CameraAccessDeniedWithoutPrompt':
        case 'CameraAccessRestricted':
          return 'Chưa có quyền camera. Hãy cho phép Camera trong Cài đặt '
              '> Ứng dụng > Cosmetic Inspector > Quyền, rồi bấm Thử lại.';
        case 'NoCamera':
          return 'Không tìm thấy camera trên thiết bị.';
      }
    }
    debugPrint('Camera error: $error');
    return 'Không mở được camera. Hãy đóng ứng dụng đang dùng camera và thử lại.';
  }

  void _onCameraChanged() {
    if (!mounted) return;
    if (_camera?.value.hasError == true) {
      setState(() {
        _cameraError = 'Camera bị gián đoạn. Hãy bấm Thử lại để kết nối lại.';
      });
    }
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _toggleFlash() async {
    final camera = _camera;
    if (!_cameraReady || camera == null || _changingFlash || _isBusy) {
      return;
    }
    _changingFlash = true;
    final enabled = !_flashTorch;
    try {
      await camera.setFlashMode(enabled ? FlashMode.torch : FlashMode.off);
      if (mounted && identical(camera, _camera)) {
        setState(() => _flashTorch = enabled);
      }
    } on CameraException catch (_) {
      _showError('Không bật được đèn flash trên camera này.');
    } finally {
      _changingFlash = false;
    }
  }

  Future<void> _onTriggerShutter() async {
    final camera = _camera;
    if (!_cameraReady || camera == null || _isBusy || _changingFlash) {
      return;
    }
    final stepIndex = _currentStepIndex;
    setState(() => _isCapturing = true);
    HapticFeedback.mediumImpact();
    try {
      final image = await camera.takePicture();
      final bytes = await image.readAsBytes();
      if (!mounted || !identical(camera, _camera) || !_cameraWanted) return;
      setState(() {
        _capturedThumbnails[stepIndex] = image.path;
        _thumbnailBytes[stepIndex] = bytes;
        _isGalleryPhoto[stepIndex] = false;
      });
      await _reviewCapturedPhoto(stepIndex);
    } catch (error) {
      debugPrint('Capture error: $error');
      _showError('Không chụp được ảnh. Hãy giữ máy ổn định và thử lại.');
    } finally {
      if (mounted) setState(() => _isCapturing = false);
    }
  }

  Future<void> _pickFromGallery({int? targetIndex}) async {
    if (_isBusy) return;
    final index = targetIndex ?? _currentStepIndex;
    setState(() {
      _isPickingGallery = true;
      _currentStepIndex = index;
    });
    _cameraWanted = false;
    try {
      await _syncCamera();
      // Keep original resolution: do NOT provide maxWidth/maxHeight/imageQuality
      final file = await _picker.pickImage(source: ImageSource.gallery);
      if (!mounted || file == null) return;

      final length = await file.length();
      if (length > 25 * 1024 * 1024) {
        _showError(
          'Dung lượng ảnh (${(length / (1024 * 1024)).toStringAsFixed(1)} MB) vượt quá giới hạn 25 MB của máy chủ.',
        );
        return;
      }

      final bytes = await file.readAsBytes();
      try {
        DamageApi.detectMimeAndFilename(file.path, bytes);
      } on DamageApiException catch (e) {
        _showError(e.message);
        return;
      }

      if (!mounted) return;
      setState(() {
        _capturedThumbnails[index] = file.path;
        _thumbnailBytes[index] = bytes;
        _isGalleryPhoto[index] = true;
      });
      await _reviewCapturedPhoto(index);
    } catch (error) {
      debugPrint('Pick gallery error: $error');
      _showError('Không thể chọn ảnh từ thư viện. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _isPickingGallery = false);
        _cameraWanted =
            WidgetsBinding.instance.lifecycleState ==
                AppLifecycleState.resumed &&
            !_analysisOpen &&
            !_reviewOpen &&
            !_historyOpen;
        await _syncCamera();
      }
    }
  }

  Future<void> _reviewCapturedPhoto(int index) async {
    final bytes = _thumbnailBytes[index];
    if (bytes == null || _reviewOpen || _isSubmitting) return;
    final fromGallery = _isGalleryPhoto[index] == true;
    setState(() {
      _reviewOpen = true;
      _currentStepIndex = index;
    });
    _cameraWanted = false;
    try {
      await _syncCamera();
      if (!mounted) return;
      ScaffoldMessenger.of(context).removeCurrentSnackBar();
      final action = await Navigator.of(context).push<PhotoReviewAction>(
        MaterialPageRoute(
          builder: (_) => PhotoReviewScreen(
            sideLabel: _steps[index].label,
            imageBytes: bytes,
            isFromGallery: fromGallery,
          ),
        ),
      );
      if (!mounted) return;
      setState(() {
        if (action == PhotoReviewAction.retake) {
          _capturedThumbnails.remove(index);
          _thumbnailBytes.remove(index);
          _isGalleryPhoto.remove(index);
          _currentStepIndex = index;
        } else if (!_hasBothPhotos) {
          _currentStepIndex = _steps.asMap().keys.firstWhere(
            (step) => !_capturedThumbnails.containsKey(step),
          );
        }
      });
    } finally {
      if (mounted) {
        setState(() => _reviewOpen = false);
        _cameraWanted =
            WidgetsBinding.instance.lifecycleState ==
                AppLifecycleState.resumed &&
            !_isPickingGallery &&
            !_historyOpen;
        await _syncCamera();
      }
    }
  }

  void _onStepSelected(int index) {
    if (_isBusy) return;
    if (_thumbnailBytes.containsKey(index)) {
      unawaited(_reviewCapturedPhoto(index));
    } else {
      setState(() => _currentStepIndex = index);
    }
  }

  Future<void> _openHistory() async {
    if (_isBusy) return;
    setState(() => _historyOpen = true);
    _cameraWanted = false;
    try {
      await _syncCamera();
      if (!mounted) return;
      await Navigator.of(context).push<void>(
        MaterialPageRoute(builder: (_) => const HistoryScreen()),
      );
    } finally {
      if (mounted) {
        setState(() => _historyOpen = false);
        _cameraWanted =
            WidgetsBinding.instance.lifecycleState ==
                AppLifecycleState.resumed &&
            !_analysisOpen &&
            !_reviewOpen &&
            !_isPickingGallery;
        await _syncCamera();
      }
    }
  }

  Future<void> _submitPhotos() async {
    if (!_hasBothPhotos || _isBusy || _changingFlash) return;
    final images = Map<InspectionStepType, String>.unmodifiable({
      for (var index = 0; index < _steps.length; index++)
        _steps[index]: _capturedThumbnails[index]!,
    });
    setState(() {
      _isSubmitting = true;
      _analysisOpen = true;
    });
    _cameraWanted = false;
    try {
      await _syncCamera();
      if (!mounted) return;
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => AnalysisScreen(
            deviceName: widget.deviceName,
            deviceImei: widget.deviceImei,
            capturedImages: images,
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
          _analysisOpen = false;
        });
        _cameraWanted =
            WidgetsBinding.instance.lifecycleState ==
                AppLifecycleState.resumed &&
            !_isPickingGallery &&
            !_historyOpen;
        await _syncCamera();
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _cameraWanted = false;
    unawaited(_syncCamera());
    super.dispose();
  }

  Widget _buildCameraViewport() {
    final camera = _camera;
    if (_cameraError != null) {
      return Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.no_photography_outlined,
                  size: 48,
                  color: AppColors.textSecondaryDark,
                ),
                const SizedBox(height: 12),
                Text(_cameraError!, textAlign: TextAlign.center),
                const SizedBox(height: 14),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    FilledButton.icon(
                      onPressed: () => unawaited(_syncCamera()),
                      icon: const Icon(Icons.refresh),
                      label: const Text('Thử lại'),
                    ),
                    const SizedBox(width: 12),
                    OutlinedButton.icon(
                      key: const ValueKey('pick-from-gallery-error-fallback'),
                      onPressed: _isBusy ? null : () => _pickFromGallery(),
                      icon: const Icon(Icons.photo_library_outlined),
                      label: const Text('Chọn từ thư viện'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      );
    }
    if (!_cameraReady || camera == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return Center(child: CameraPreview(camera));
  }

  @override
  Widget build(BuildContext context) {
    final activeStep = _steps[_currentStepIndex];
    final isReady = _cameraReady && !_isBusy;

    return Scaffold(
      backgroundColor: AppColors.darkCanvas,
      body: SafeArea(
        child: Stack(
          children: [
            // 1. Camera Viewport
            Positioned.fill(
              top: _cameraError != null ? 140 : 0,
              bottom: _cameraError != null ? 330 : 0,
              child: _buildCameraViewport(),
            ),

            // 2. Khung ngắm căn chỉnh quang học
            if (_gridVisible && _cameraReady)
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
                        key: const ValueKey('open-history-button'),
                        style: IconButton.styleFrom(
                          backgroundColor: AppColors.darkSurface.withValues(
                            alpha: 0.8,
                          ),
                          minimumSize: const Size(44, 44),
                        ),
                        icon: const Icon(
                          Icons.history,
                          size: 20,
                          color: Colors.white,
                        ),
                        tooltip: 'Xem lịch sử quét',
                        onPressed: _isBusy ? null : _openHistory,
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
                              backgroundColor: AppColors.darkSurface.withValues(
                                alpha: 0.8,
                              ),
                            ),
                            icon: Icon(
                              _flashTorch ? Icons.flash_on : Icons.flash_off,
                              size: 18,
                              color: _flashTorch
                                  ? AppColors.amberAccent
                                  : Colors.white,
                            ),
                            tooltip: 'Bật/tắt đèn flash',
                            onPressed: isReady ? _toggleFlash : null,
                          ),
                          const SizedBox(width: 6),
                          IconButton(
                            style: IconButton.styleFrom(
                              backgroundColor: AppColors.darkSurface.withValues(
                                alpha: 0.8,
                              ),
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
                  Text(
                    'Chụp hoặc chọn ảnh 2 mặt, xem lại rồi bấm gửi',
                    style: AppTypography.bodyMedium,
                  ),
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
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.darkSurface.withValues(alpha: 0.9),
                    border: Border.all(color: AppColors.darkBorder),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.compass_calibration_outlined,
                        size: 14,
                        color: AppColors.amberAccent,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        'HƯỚNG: ${activeStep.label.toUpperCase()}',
                        style: AppTypography.labelCaps.copyWith(
                          color: Colors.white,
                        ),
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
                  color: AppColors.darkCanvas.withValues(alpha: 0.95),
                  border: const Border(
                    top: BorderSide(
                      color: AppColors.darkBorderSubtle,
                      width: 1,
                    ),
                  ),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    StepThumbnailTray(
                      steps: _steps,
                      activeIndex: _currentStepIndex,
                      capturedThumbnails: _capturedThumbnails,
                      thumbnailBytes: _thumbnailBytes,
                      onStepSelected: _onStepSelected,
                    ),
                    const SizedBox(height: 14),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          DropdownButtonHideUnderline(
                            child: DropdownButton<DeviceProfile>(
                              value: _currentProfile,
                              dropdownColor: AppColors.darkSurfaceElevated,
                              icon: const Icon(
                                Icons.arrow_drop_down,
                                color: AppColors.textSecondaryDark,
                              ),
                              items: const [
                                DropdownMenuItem(
                                  value: DeviceProfile.smartphone,
                                  child: Text(
                                    'Smartphone',
                                    style: TextStyle(fontSize: 12),
                                  ),
                                ),
                                DropdownMenuItem(
                                  value: DeviceProfile.keyboard,
                                  child: Text(
                                    'Bàn phím',
                                    style: TextStyle(fontSize: 12),
                                  ),
                                ),
                                DropdownMenuItem(
                                  value: DeviceProfile.laptop,
                                  child: Text(
                                    'Laptop',
                                    style: TextStyle(fontSize: 12),
                                  ),
                                ),
                              ],
                              onChanged: (val) {
                                if (val != null) {
                                  setState(() => _currentProfile = val);
                                }
                              },
                            ),
                          ),
                          GestureDetector(
                            key: const ValueKey('capture-shutter'),
                            onTap: isReady ? _onTriggerShutter : null,
                            child: Container(
                              width: 76,
                              height: 76,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: isReady
                                      ? AppColors.amberAccent
                                      : AppColors.darkBorder,
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
                                  child: _isCapturing
                                      ? const Padding(
                                          padding: EdgeInsets.all(16),
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                          ),
                                        )
                                      : isReady
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
                            tooltip: 'Chụp/chọn lại góc này',
                            icon: const Icon(Icons.replay),
                            onPressed: _isBusy
                                ? null
                                : () {
                                    setState(() {
                                      _capturedThumbnails.remove(
                                        _currentStepIndex,
                                      );
                                      _thumbnailBytes.remove(_currentStepIndex);
                                      _isGalleryPhoto.remove(_currentStepIndex);
                                    });
                                    HapticFeedback.selectionClick();
                                  },
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 10),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Column(
                        children: [
                          SizedBox(
                            width: double.infinity,
                            child: OutlinedButton.icon(
                              key: const ValueKey('pick-from-gallery-button'),
                              onPressed: _isBusy
                                  ? null
                                  : () => _pickFromGallery(
                                        targetIndex: _currentStepIndex,
                                      ),
                              icon: const Icon(
                                Icons.photo_library_outlined,
                                size: 18,
                              ),
                              label: Text(
                                'Chọn ảnh thư viện (${activeStep.label})',
                              ),
                            ),
                          ),
                          const SizedBox(height: 8),
                          SizedBox(
                            width: double.infinity,
                            child: FilledButton.icon(
                              key: const ValueKey('submit-photos'),
                              onPressed: _hasBothPhotos && !_isBusy
                                  ? _submitPhotos
                                  : null,
                              icon: const Icon(Icons.send_outlined),
                              label: Text(
                                'Gửi để phân tích (${_capturedThumbnails.length}/2)',
                              ),
                            ),
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
