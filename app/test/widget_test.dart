import 'dart:async';
import 'dart:convert';

import 'package:camera/camera.dart';
import 'package:camera_platform_interface/camera_platform_interface.dart';
import 'package:cosmetic_inspector/features/inspection/models/capture_condition.dart';
import 'package:cosmetic_inspector/features/inspection/presentation/analysis_screen.dart';
import 'package:cosmetic_inspector/features/inspection/presentation/photo_review_screen.dart';
import 'package:cosmetic_inspector/features/inspection/presentation/widgets/thumbnail_step_tray.dart';
import 'package:cosmetic_inspector/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

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
  late TestCameraPlatform camera;
  late CameraPlatform previousPlatform;

  setUp(() {
    previousPlatform = CameraPlatform.instance;
    camera = TestCameraPlatform();
    CameraPlatform.instance = camera;
  });

  tearDown(() => CameraPlatform.instance = previousPlatform);

  Future<void> mountApp(WidgetTester tester) async {
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    addTearDown(() async {
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    });
    await tester.pumpWidget(const CosmeticInspectorApp());
    await tester.pumpAndSettle();
  }

  Finder getSubmitButton() => find.byKey(const ValueKey('submit-photos'));

  Future<void> keepPhoto(WidgetTester tester) async {
    expect(find.byType(PhotoReviewScreen), findsOneWidget);
    expect(find.byType(InteractiveViewer), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('review-keep')));
    await tester.pumpAndSettle();
  }

  Future<void> captureAndKeep(WidgetTester tester) async {
    await tester.tap(find.byKey(const ValueKey('capture-shutter')));
    await tester.pumpAndSettle();
    await keepPhoto(tester);
  }

  testWidgets('Opens rear camera without requesting audio', (tester) async {
    await mountApp(tester);
    expect(find.textContaining('SN/IMEI'), findsOneWidget);
    expect(find.byType(CameraPreview), findsOneWidget);
    expect(camera.selectedCamera, TestCameraPlatform.back);
    expect(camera.audioEnabled, isFalse);
    expect(camera.flashMode, FlashMode.off);
  });

  for (final backFirst in [false, true]) {
    testWidgets(
      'Reviews both sides and analyzes only after submit with backFirst=$backFirst',
      (tester) async {
        await mountApp(tester);
        final tray = find.byType(StepThumbnailTray);
        expect(tester.widget<StepThumbnailTray>(tray).steps, hasLength(2));
        expect(
          tester.widget<FilledButton>(getSubmitButton()).onPressed,
          isNull,
        );
        if (backFirst) {
          await tester.tap(find.text('Mặt sau'));
          await tester.pumpAndSettle();
        }
        final shutter = find.byKey(const ValueKey('capture-shutter'));
        await tester.tap(shutter);
        await tester.pumpAndSettle();
        expect(
          tester
              .widget<PhotoReviewScreen>(find.byType(PhotoReviewScreen))
              .sideLabel,
          backFirst ? 'Mặt sau' : 'Mặt trước',
        );
        expect(find.byKey(const ValueKey('review-photo')), findsOneWidget);
        expect(find.byType(AnalysisScreen), findsNothing);
        await keepPhoto(tester);
        expect(find.text('Đã chụp'), findsOneWidget);
        expect(
          tester.widget<StepThumbnailTray>(tray).activeIndex,
          backFirst ? 0 : 1,
        );
        expect(
          tester
              .widget<StepThumbnailTray>(tray)
              .capturedThumbnails
              .values
              .single,
          '/capture-1.png',
        );
        expect(find.byType(Image), findsOneWidget);
        expect(
          tester.widget<FilledButton>(getSubmitButton()).onPressed,
          isNull,
        );

        await tester.tap(shutter);
        await tester.pumpAndSettle();
        await keepPhoto(tester);
        await tester.pump(const Duration(seconds: 5));
        expect(find.byType(AnalysisScreen), findsNothing);
        expect(find.byType(StepThumbnailTray), findsOneWidget);
        expect(
          tester.widget<FilledButton>(getSubmitButton()).onPressed,
          isNotNull,
        );
        final submit = tester
            .widget<FilledButton>(getSubmitButton())
            .onPressed!;
        await tester.tap(getSubmitButton());
        // A queued duplicate event must not open another analysis screen.
        submit();
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 350));
        final analysis = tester.widget<AnalysisScreen>(
          find.byType(AnalysisScreen),
        );
        expect(
          analysis.capturedImages[InspectionStepType.front],
          backFirst ? '/capture-2.png' : '/capture-1.png',
        );
        expect(
          analysis.capturedImages[InspectionStepType.back],
          backFirst ? '/capture-1.png' : '/capture-2.png',
        );
        expect(camera.captures, 2);
        expect(camera.releases, 3);
      },
    );
  }

  testWidgets('Permission denial disables capture and can be retried', (
    tester,
  ) async {
    camera.openError = CameraException('CameraAccessDenied', 'Denied');
    await mountApp(tester);
    expect(find.textContaining('Chưa có quyền camera'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('capture-shutter')));
    expect(camera.captures, 0);
    camera.openError = null;
    await tester.ensureVisible(find.text('Thử lại'));
    await tester.tap(find.text('Thử lại'));
    await tester.pumpAndSettle();
    expect(find.byType(CameraPreview), findsOneWidget);
  });

  testWidgets('Reports missing camera', (tester) async {
    camera.cameras = [];
    await mountApp(tester);
    expect(find.text('Không tìm thấy camera trên thiết bị.'), findsOneWidget);
    expect(find.byType(CameraPreview), findsNothing);
  });

  testWidgets('Failed capture keeps the current side available for retry', (
    tester,
  ) async {
    camera.captureFails = true;
    await mountApp(tester);
    await tester.tap(find.byKey(const ValueKey('capture-shutter')));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<StepThumbnailTray>(find.byType(StepThumbnailTray))
          .capturedThumbnails,
      isEmpty,
    );
    expect(find.textContaining('Không chụp được ảnh'), findsOneWidget);
    camera.captureFails = false;
    await tester.tap(find.byKey(const ValueKey('capture-shutter')));
    await tester.pumpAndSettle();
    await keepPhoto(tester);
    expect(find.text('Đã chụp'), findsOneWidget);
  });

  testWidgets('Ignores repeated taps while a photo is being captured', (
    tester,
  ) async {
    await mountApp(tester);
    camera.captureGate = Completer<void>();
    final shutter = find.byKey(const ValueKey('capture-shutter'));
    await tester.tap(shutter);
    await tester.pump();
    await tester.tap(shutter);
    expect(camera.captures, 1);
    camera.captureGate!.complete();
    await tester.pumpAndSettle();
    await keepPhoto(tester);
    expect(find.text('Đã chụp'), findsOneWidget);
  });

  testWidgets('Reopens a saved photo and replaces only the side retaken', (
    tester,
  ) async {
    await mountApp(tester);
    await captureAndKeep(tester);
    await captureAndKeep(tester);
    await tester.tap(find.text('Mặt trước'));
    await tester.pumpAndSettle();
    expect(find.text('Xem lại · Mặt trước'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('review-retake')));
    await tester.pumpAndSettle();

    final tray = find.byType(StepThumbnailTray);
    var state = tester.widget<StepThumbnailTray>(tray);
    expect(state.activeIndex, 0);
    expect(state.capturedThumbnails, {1: '/capture-2.png'});
    expect(state.thumbnailBytes.keys, [1]);
    expect(tester.widget<FilledButton>(getSubmitButton()).onPressed, isNull);

    await captureAndKeep(tester);
    state = tester.widget<StepThumbnailTray>(tray);
    expect(state.capturedThumbnails, {
      0: '/capture-3.png',
      1: '/capture-2.png',
    });
    await tester.tap(getSubmitButton());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 350));
    expect(
      tester.widget<AnalysisScreen>(find.byType(AnalysisScreen)).capturedImages,
      {
        InspectionStepType.front: '/capture-3.png',
        InspectionStepType.back: '/capture-2.png',
      },
    );
  });

  testWidgets('Retake immediately after capture requires a new photo', (
    tester,
  ) async {
    await mountApp(tester);
    await tester.tap(find.byKey(const ValueKey('capture-shutter')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('review-retake')));
    await tester.pumpAndSettle();
    final state = tester.widget<StepThumbnailTray>(
      find.byType(StepThumbnailTray),
    );
    expect(state.capturedThumbnails, isEmpty);
    expect(state.activeIndex, 0);
    expect(tester.widget<FilledButton>(getSubmitButton()).onPressed, isNull);
    expect(find.byType(CameraPreview), findsOneWidget);
  });

  testWidgets('Photo review and submit controls fit a phone screen', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await mountApp(tester);
    await captureAndKeep(tester);
    await captureAndKeep(tester);
    expect(tester.widget<FilledButton>(getSubmitButton()).onPressed, isNotNull);
    expect(getSubmitButton().hitTestable(), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'Keeps review open across app lifecycle changes without opening camera',
    (tester) async {
      await mountApp(tester);
      await tester.tap(find.byKey(const ValueKey('capture-shutter')));
      await tester.pumpAndSettle();
      final sessions = camera.sessions;
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      await tester.pump();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(camera.sessions, sessions);
      expect(find.byType(PhotoReviewScreen), findsOneWidget);
      await keepPhoto(tester);
      expect(camera.sessions, sessions + 1);
    },
  );

  testWidgets('Controls flash and reopens camera after backgrounding', (
    tester,
  ) async {
    await mountApp(tester);
    await tester.tap(find.byTooltip('Bật/tắt đèn flash'));
    await tester.pumpAndSettle();
    expect(camera.flashMode, FlashMode.torch);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    await tester.pump();
    expect(camera.releases, 1);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();
    expect(camera.sessions, 2);
    expect(find.byType(CameraPreview), findsOneWidget);
    expect(camera.flashMode, FlashMode.off);
  });

  testWidgets('Handles lifecycle changes during camera initialization', (
    tester,
  ) async {
    camera.initializeGate = Completer<void>();
    await tester.pumpWidget(const CosmeticInspectorApp());
    await tester.pump();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    camera.initializeGate!.complete();
    await tester.pumpAndSettle();
    expect(camera.sessions, 1);
    expect(find.byType(CameraPreview), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    expect(camera.releases, 1);
  });
}
