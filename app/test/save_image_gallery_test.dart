import 'dart:typed_data';
import 'package:cosmetic_inspector/features/inspection/data/damage_api.dart';
import 'package:cosmetic_inspector/features/inspection/data/gallery_saver_service.dart';
import 'package:cosmetic_inspector/features/inspection/models/capture_condition.dart';
import 'package:cosmetic_inspector/features/inspection/presentation/result_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class FakeGallerySaver implements GallerySaverService {
  Uint8List? savedBytes;
  String? savedFileName;
  bool shouldThrowAccessDenied = false;

  @override
  Future<void> saveImageBytes({
    required Uint8List bytes,
    required String fileName,
  }) async {
    if (shouldThrowAccessDenied) {
      throw const GallerySaverException(
        'Quyền truy cập thư viện ảnh bị từ chối. Vui lòng cấp quyền trong Cài đặt thiết bị.',
      );
    }
    savedBytes = bytes;
    savedFileName = fileName;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late FakeGallerySaver fakeSaver;

  setUp(() {
    fakeSaver = FakeGallerySaver();
  });

  final sampleScanResult = {
    'scanId': '11112222-3333-4444-5555-666677778888',
    'status': 'estimated',
    'hasDefect': true,
    'damage': {
      'status': 'candidates',
      'candidate_pixels_original': 1200,
      'found': true,
      'observed_surface': 'front',
    },
    'severity': {
      'status': 'estimated',
      'estimated_severity': 'minor',
      'needs_review': false,
      'area_ratio': 0.05,
      'skeleton_length_ratio': 0.12,
      'width_ratio': 0.03,
      'reasons': ['area_ratio:minor'],
    },
    'assets': {
      'source': '/api/damage-assets/11112222-3333-4444-5555-666677778888/source.png',
      'overlay': '/api/damage-assets/11112222-3333-4444-5555-666677778888/overlay.png',
    },
  };

  testWidgets('Saves source image to gallery with formatted filename and shows confirmation', (tester) async {
    final mockClient = MockClient((request) async {
      if (request.url.path.contains('/source.png')) {
        return http.Response.bytes([137, 80, 78, 71, 1, 2, 3], 200, headers: {'content-type': 'image/png'});
      }
      return http.Response('Not found', 404);
    });

    final api = DamageApi(client: mockClient);

    await tester.pumpWidget(
      MaterialApp(
        home: ResultScreen(
          deviceName: 'Apple iPhone 13 Pro',
          results: {InspectionStepType.front: sampleScanResult},
          gallerySaver: fakeSaver,
          damageApi: api,
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Tap "Lưu ảnh" button
    await tester.tap(find.byKey(const ValueKey('save-image-btn-front')));
    await tester.pumpAndSettle();

    // Modal sheet opens with options
    expect(find.text('Ảnh nguồn (gốc)'), findsOneWidget);
    expect(find.text('Ảnh có vùng đánh dấu (overlay)'), findsOneWidget);

    // Tap source option
    await tester.tap(find.byKey(const ValueKey('save-source-option')));
    await tester.pumpAndSettle();

    // Verify image was saved
    expect(fakeSaver.savedBytes, isNotNull);
    expect(fakeSaver.savedBytes!.length, 7);
    expect(fakeSaver.savedFileName, contains('scan_11112222_Mặt_trước_source'));
    expect(find.text('Đã lưu vào thư viện ảnh'), findsOneWidget);
  });

  testWidgets('Saves overlay image to gallery successfully', (tester) async {
    final mockClient = MockClient((request) async {
      if (request.url.path.contains('/overlay.png')) {
        return http.Response.bytes([137, 80, 78, 71, 9, 8, 7], 200, headers: {'content-type': 'image/png'});
      }
      return http.Response('Not found', 404);
    });

    final api = DamageApi(client: mockClient);

    await tester.pumpWidget(
      MaterialApp(
        home: ResultScreen(
          deviceName: 'Apple iPhone 13 Pro',
          results: {InspectionStepType.front: sampleScanResult},
          gallerySaver: fakeSaver,
          damageApi: api,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('save-image-btn-front')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('save-overlay-option')));
    await tester.pumpAndSettle();

    expect(fakeSaver.savedBytes, isNotNull);
    expect(fakeSaver.savedFileName, contains('scan_11112222_Mặt_trước_overlay'));
    expect(find.text('Đã lưu vào thư viện ảnh'), findsOneWidget);
  });

  testWidgets('Disables overlay option when scan result has no overlay asset', (tester) async {
    final resultWithoutOverlay = {
      ...sampleScanResult,
      'assets': {
        'source': '/api/damage-assets/11112222-3333-4444-5555-666677778888/source.png',
      },
    };

    final api = DamageApi(client: MockClient((_) async => http.Response('', 200)));

    await tester.pumpWidget(
      MaterialApp(
        home: ResultScreen(
          deviceName: 'Apple iPhone 13 Pro',
          results: {InspectionStepType.front: resultWithoutOverlay},
          gallerySaver: fakeSaver,
          damageApi: api,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('save-image-btn-front')));
    await tester.pumpAndSettle();

    final overlayTile = tester.widget<ListTile>(find.byKey(const ValueKey('save-overlay-option')));
    expect(overlayTile.enabled, isFalse);
    expect(find.textContaining('Không có ảnh đánh dấu'), findsOneWidget);
  });

  testWidgets('Permission denial displays error and preserves inspection screen', (tester) async {
    fakeSaver.shouldThrowAccessDenied = true;
    final mockClient = MockClient((request) async =>
        http.Response.bytes([137, 80, 78, 71], 200, headers: {'content-type': 'image/png'}));
    final api = DamageApi(client: mockClient);

    await tester.pumpWidget(
      MaterialApp(
        home: ResultScreen(
          deviceName: 'Apple iPhone 13 Pro',
          results: {InspectionStepType.front: sampleScanResult},
          gallerySaver: fakeSaver,
          damageApi: api,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('save-image-btn-front')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('save-source-option')));
    await tester.pumpAndSettle();

    expect(find.textContaining('Quyền truy cập thư viện ảnh bị từ chối'), findsOneWidget);
    // Result screen content is still visible
    expect(find.text('Mặt trước'), findsOneWidget);
    expect(find.textContaining('Mức độ hư hại ước tính'), findsWidgets);
  });
}
