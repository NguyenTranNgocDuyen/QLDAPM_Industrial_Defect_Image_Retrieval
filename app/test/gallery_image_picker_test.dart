import 'dart:async';
import 'dart:convert';

import 'package:camera_platform_interface/camera_platform_interface.dart';
import 'package:cosmetic_inspector/features/inspection/presentation/capture_screen.dart';
import 'package:cosmetic_inspector/features/inspection/presentation/photo_review_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';

class FakeImagePicker extends ImagePicker {
  XFile? nextFile;
  LostDataResponse lostDataResponse = LostDataResponse.empty();
  int pickCallCount = 0;

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) async {
    pickCallCount++;
    return nextFile;
  }

  @override
  Future<LostDataResponse> retrieveLostData() async => lostDataResponse;
}

class TestCameraPlatform extends CameraPlatform {
  static const back = CameraDescription(
    name: 'back',
    lensDirection: CameraLensDirection.back,
    sensorOrientation: 90,
  );
  static const front = CameraDescription(
    name: 'front',
    lensDirection: CameraLensDirection.front,
    sensorOrientation: 90,
  );

  List<CameraDescription> cameras = [front, back];
  CameraException? openError;
  bool captureFails = false;
  int captures = 0;
  int sessions = 0;
  int releases = 0;
  CameraDescription? selectedCamera;
  bool? audioEnabled;
  FlashMode? flashMode;
  Completer<void>? captureGate;
  Completer<void>? initializeGate;
  final errors = StreamController<CameraErrorEvent>.broadcast();

  @override
  Future<List<CameraDescription>> availableCameras() async => cameras;

  @override
  Future<int> createCamera(
    CameraDescription cameraDescription,
    ResolutionPreset? resolutionPreset, {
    bool enableAudio = false,
  }) async {
    if (openError case final error?) throw error;
    selectedCamera = cameraDescription;
    audioEnabled = enableAudio;
    return ++sessions;
  }

  @override
  Future<void> initializeCamera(
    int cameraId, {
    ImageFormatGroup imageFormatGroup = ImageFormatGroup.unknown,
  }) async {
    await initializeGate?.future;
  }

  @override
  Stream<CameraInitializedEvent> onCameraInitialized(int cameraId) =>
      Stream.value(
        CameraInitializedEvent(
          cameraId,
          1280,
          720,
          ExposureMode.auto,
          true,
          FocusMode.auto,
          true,
        ),
      );

  @override
  Stream<CameraErrorEvent> onCameraError(int cameraId) => errors.stream;

  @override
  Stream<DeviceOrientationChangedEvent> onDeviceOrientationChanged() =>
      Stream.value(
        const DeviceOrientationChangedEvent(DeviceOrientation.portraitUp),
      );

  @override
  Widget buildPreview(int cameraId) => const ColoredBox(color: Colors.blue);

  @override
  Future<void> setFlashMode(int cameraId, FlashMode mode) async =>
      flashMode = mode;

  @override
  Future<XFile> takePicture(int cameraId) async {
    captures++;
    await captureGate?.future;
    if (captureFails) {
      throw PlatformException(code: 'CaptureFailed', message: 'Camera busy');
    }
    return XFile.fromData(
      base64Decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==',
      ),
      path: '/capture-$captures.png',
      mimeType: 'image/png',
    );
  }

  @override
  Future<void> dispose(int cameraId) async => releases++;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late TestCameraPlatform camera;
  late CameraPlatform previousPlatform;
  late FakeImagePicker fakePicker;

  setUp(() {
    previousPlatform = CameraPlatform.instance;
    camera = TestCameraPlatform();
    CameraPlatform.instance = camera;
    fakePicker = FakeImagePicker();
  });

  tearDown(() {
    CameraPlatform.instance = previousPlatform;
  });

  Future<void> mountCaptureScreen(WidgetTester tester) async {
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    addTearDown(() async {
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    });
    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(
          imagePicker: fakePicker,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('PhotoReviewScreen displays "Chọn lại" when isFromGallery is true', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: PhotoReviewScreen(
          sideLabel: 'Mặt trước',
          imageBytes: Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 1, 2]),
          isFromGallery: true,
        ),
      ),
    );
    expect(find.text('Chọn lại'), findsOneWidget);
    expect(find.text('Chụp lại'), findsNothing);
    expect(find.text('Giữ ảnh này'), findsOneWidget);
  });

  testWidgets('PhotoReviewScreen displays "Chụp lại" when isFromGallery is false', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: PhotoReviewScreen(
          sideLabel: 'Mặt trước',
          imageBytes: Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 1, 2]),
          isFromGallery: false,
        ),
      ),
    );
    expect(find.text('Chụp lại'), findsOneWidget);
    expect(find.text('Chọn lại'), findsNothing);
  });

  testWidgets('Picks JPEG from gallery, reviews with "Chọn lại", and keeps photo', (tester) async {
    fakePicker.nextFile = XFile.fromData(
      Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 10, 20, 30, 40]),
      name: 'front_phone.jpg',
      path: 'front_phone.jpg',
    );

    await mountCaptureScreen(tester);

    // Tap gallery button
    await tester.tap(find.byKey(const ValueKey('pick-from-gallery-button')));
    await tester.pumpAndSettle();

    // Now in PhotoReviewScreen
    expect(find.byType(PhotoReviewScreen), findsOneWidget);
    expect(find.text('Chọn lại'), findsOneWidget);

    // Keep photo
    await tester.tap(find.byKey(const ValueKey('review-keep')));
    await tester.pumpAndSettle();

    // Capture screen should now show 1 photo kept (switched to back slot)
    expect(find.text('HƯỚNG: MẶT SAU'), findsOneWidget);
  });

  testWidgets('Canceling gallery picker does not alter existing slot photo', (tester) async {
    fakePicker.nextFile = null; // User cancelled

    await mountCaptureScreen(tester);

    await tester.tap(find.byKey(const ValueKey('pick-from-gallery-button')));
    await tester.pumpAndSettle();

    expect(find.byType(PhotoReviewScreen), findsNothing);
    expect(find.text('Gửi để phân tích (0/2)'), findsOneWidget);
  });

  testWidgets('Accepts WebP format from gallery and opens PhotoReviewScreen', (tester) async {
    // WebP magic: RIFF....WEBP
    final webpBytes = Uint8List.fromList([
      0x52, 0x49, 0x46, 0x46, 0, 0, 0, 0, 0x57, 0x45, 0x42, 0x50, 1, 2
    ]);
    fakePicker.nextFile = XFile.fromData(webpBytes, name: 'sample.webp', path: 'sample.webp');

    await mountCaptureScreen(tester);

    await tester.tap(find.byKey(const ValueKey('pick-from-gallery-button')));
    await tester.pumpAndSettle();

    // WebP is accepted and opens PhotoReviewScreen
    expect(find.byType(PhotoReviewScreen), findsOneWidget);
    expect(find.text('Chọn lại'), findsOneWidget);
  });

  testWidgets('Rejects unsupported formats like HEIC with informative message', (tester) async {
    // HEIC ftyp header: ....ftypheic
    final heicBytes = Uint8List.fromList([
      0x00, 0x00, 0x00, 0x18, 0x66, 0x74, 0x79, 0x70, 0x68, 0x65, 0x69, 0x63
    ]);
    fakePicker.nextFile = XFile.fromData(heicBytes, name: 'sample.heic', path: 'sample.heic');

    await mountCaptureScreen(tester);

    await tester.tap(find.byKey(const ValueKey('pick-from-gallery-button')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    // Should stay on CaptureScreen and show SnackBar error
    expect(find.byType(PhotoReviewScreen), findsNothing);
    expect(find.textContaining('HEIC/HEIF chưa được máy chủ hỗ trợ'), findsOneWidget);
  });

  testWidgets('Combines camera photo and gallery photo for full 2-photo analysis', (tester) async {
    await mountCaptureScreen(tester);

    // 1. Take camera photo for front
    await tester.tap(find.byKey(const ValueKey('capture-shutter')));
    await tester.pumpAndSettle();
    expect(find.byType(PhotoReviewScreen), findsOneWidget);
    expect(find.text('Chụp lại'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('review-keep')));
    await tester.pumpAndSettle();

    // Now on back slot
    expect(find.text('HƯỚNG: MẶT SAU'), findsOneWidget);

    // 2. Pick gallery photo for back
    fakePicker.nextFile = XFile.fromData(
      Uint8List.fromList([0x89, 0x50, 0x4E, 0x47, 13, 10, 26, 10]),
      name: 'back_phone.png',
      path: 'back_phone.png',
    );
    await tester.tap(find.byKey(const ValueKey('pick-from-gallery-button')));
    await tester.pumpAndSettle();

    expect(find.byType(PhotoReviewScreen), findsOneWidget);
    expect(find.text('Chọn lại'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('review-keep')));
    await tester.pumpAndSettle();

    // Both photos are present! Submit button is enabled
    expect(find.text('Gửi để phân tích (2/2)'), findsOneWidget);
    final submitFinder = find.byKey(const ValueKey('submit-photos'));
    expect(tester.widget<FilledButton>(submitFinder).onPressed, isNotNull);
  });
}
