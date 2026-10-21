import 'dart:convert';
import 'package:cosmetic_inspector/features/inspection/data/damage_api.dart';
import 'package:cosmetic_inspector/features/inspection/presentation/history_screen.dart';
import 'package:cosmetic_inspector/features/inspection/presentation/result_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final sampleDatesJson = [
    {
      'date': '2026-10-20',
      'sessionCount': 1,
      'scanCount': 2,
      'hasDefectCount': 1,
    },
  ];

  final sampleSessionsJson = [
    {
      'sessionId': '1be7d7ec-3bc8-48ae-b301-5801cdaee8db',
      'createdAt': '2026-10-20T13:52:05.30873Z',
      'deviceInfo': 'iPhone 15 Pro',
      'hasDefect': true,
      'overallSeverity': 'severe',
      'needsReview': true,
      'frontScan': {
        'scanId': '1be7d7ec-3bc8-48ae-b301-5801cdaee8db',
        'originalFilename': 'capture_front.jpg',
        'displayImageUrl': '/api/damage-assets/10efad78-0d4d-45f6-943c-34bf7901bd0e/overlay.png',
        'sourceImageUrl': '/api/damage-assets/10efad78-0d4d-45f6-943c-34bf7901bd0e/source.png',
        'hasDefect': true,
        'detectionCount': 0,
        'status': 'estimated',
        'surface': 'front',
        'estimatedSeverity': 'severe',
        'needsReview': true,
        'totalMs': 1562.3,
        'createdAt': '2026-10-20T13:52:05.30873Z',
      },
      'backScan': {
        'scanId': '2be7d7ec-3bc8-48ae-b301-5801cdaee8dc',
        'originalFilename': 'capture_back.jpg',
        'displayImageUrl': '/api/damage-assets/10efad78-0d4d-45f6-943c-34bf7901bd0e/overlay.png',
        'sourceImageUrl': '/api/damage-assets/10efad78-0d4d-45f6-943c-34bf7901bd0e/source.png',
        'hasDefect': false,
        'detectionCount': 0,
        'status': 'no_detected_damage',
        'surface': 'back',
        'estimatedSeverity': null,
        'needsReview': false,
        'totalMs': 1200.0,
        'createdAt': '2026-10-20T13:52:08.30873Z',
      },
      'otherScans': [],
    },
  ];

  final sampleFrontDetailJson = {
    'scanId': '1be7d7ec-3bc8-48ae-b301-5801cdaee8db',
    'success': true,
    'hasDefect': true,
    'status': 'estimated',
    'damage': {
      'status': 'candidates',
      'candidate_pixels_original': 36344,
      'found': true,
      'observed_surface': 'front',
    },
    'severity': {
      'status': 'estimated',
      'estimated_severity': 'severe',
      'needs_review': true,
      'reasons': ['area_ratio:severe'],
    },
    'assets': {
      'source': '/api/damage-assets/10efad78-0d4d-45f6-943c-34bf7901bd0e/source.png',
      'overlay': '/api/damage-assets/10efad78-0d4d-45f6-943c-34bf7901bd0e/overlay.png',
    },
  };

  final sampleBackDetailJson = {
    'scanId': '2be7d7ec-3bc8-48ae-b301-5801cdaee8dc',
    'success': true,
    'hasDefect': false,
    'status': 'no_detected_damage',
    'damage': {
      'status': 'below_alarm_threshold',
      'candidate_pixels_original': 0,
      'found': false,
      'observed_surface': 'back',
    },
    'severity': {
      'status': 'below_alarm_threshold',
      'estimated_severity': null,
      'needs_review': false,
      'reasons': [],
    },
    'assets': {
      'source': '/api/damage-assets/10efad78-0d4d-45f6-943c-34bf7901bd0e/source.png',
      'overlay': '/api/damage-assets/10efad78-0d4d-45f6-943c-34bf7901bd0e/overlay.png',
    },
  };

  testWidgets('Renders scan history grouped by date and lazily fetches sessions', (tester) async {
    int dateCalls = 0;
    int sessionCalls = 0;

    final mockClient = MockClient((request) async {
      if (request.url.path == '/api/scans/dates') {
        dateCalls++;
        return http.Response(jsonEncode(sampleDatesJson), 200, headers: {'content-type': 'application/json'});
      }
      if (request.url.path == '/api/scans/sessions') {
        sessionCalls++;
        return http.Response(jsonEncode(sampleSessionsJson), 200, headers: {'content-type': 'application/json'});
      }
      return http.Response('Not found', 404);
    });

    final api = DamageApi(client: mockClient);

    await tester.pumpWidget(
      MaterialApp(
        home: HistoryScreen(damageApi: api),
      ),
    );
    await tester.pumpAndSettle();

    // Verify date header
    expect(find.textContaining('20/10/2026'), findsOneWidget);
    expect(find.text('1 lượt kiểm tra · 2 ảnh'), findsOneWidget);
    expect(find.text('1 có ứng viên'), findsOneWidget);

    // Verify sessions loaded lazily
    expect(dateCalls, 1);
    expect(sessionCalls, 1);
    expect(find.text('iPhone 15 Pro'), findsOneWidget);
    expect(find.text('Mặt trước'), findsOneWidget);
    expect(find.text('Mặt sau'), findsOneWidget);
    expect(find.text('Xem cả 2 mặt'), findsOneWidget);
    expect(find.textContaining('Nặng · Ước tính · Cần kiểm tra'), findsOneWidget);
  });

  testWidgets('Tapping a session card fetches details for both surfaces and shows both in ResultScreen', (tester) async {
    int frontDetailCalls = 0;
    int backDetailCalls = 0;

    final mockClient = MockClient((request) async {
      if (request.url.path == '/api/scans/dates') {
        return http.Response(jsonEncode(sampleDatesJson), 200, headers: {'content-type': 'application/json'});
      }
      if (request.url.path == '/api/scans/sessions') {
        return http.Response(jsonEncode(sampleSessionsJson), 200, headers: {'content-type': 'application/json'});
      }
      if (request.url.path == '/api/scans/1be7d7ec-3bc8-48ae-b301-5801cdaee8db') {
        frontDetailCalls++;
        return http.Response(jsonEncode(sampleFrontDetailJson), 200, headers: {'content-type': 'application/json'});
      }
      if (request.url.path == '/api/scans/2be7d7ec-3bc8-48ae-b301-5801cdaee8dc') {
        backDetailCalls++;
        return http.Response(jsonEncode(sampleBackDetailJson), 200, headers: {'content-type': 'application/json'});
      }
      return http.Response('Not found', 404);
    });

    final api = DamageApi(client: mockClient);

    await tester.pumpWidget(
      MaterialApp(
        home: HistoryScreen(damageApi: api),
      ),
    );
    await tester.pumpAndSettle();

    // Tap the session card
    await tester.tap(find.text('iPhone 15 Pro'));
    await tester.pumpAndSettle();

    // Verify navigates to ResultScreen
    expect(find.byType(ResultScreen), findsOneWidget);
    expect(find.text('iPhone 15 Pro'), findsOneWidget);

    // Verify front card is visible
    expect(find.text('Mặt trước'), findsWidgets);
    expect(find.textContaining('Mức độ hư hại ước tính'), findsWidgets);

    // Scroll to see the back surface card
    await tester.scrollUntilVisible(
      find.text('Mặt sau'),
      300,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('Mặt sau'), findsOneWidget);

    // Assert both front and back details were fetched
    expect(frontDetailCalls, 1);
    expect(backDetailCalls, 1);
  });

  testWidgets('Displays empty history state when server returns empty date list', (tester) async {
    final mockClient = MockClient((request) async {
      if (request.url.path == '/api/scans/dates') {
        return http.Response('[]', 200, headers: {'content-type': 'application/json'});
      }
      return http.Response('Not found', 404);
    });

    final api = DamageApi(client: mockClient);

    await tester.pumpWidget(
      MaterialApp(
        home: HistoryScreen(damageApi: api),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Chưa có lượt quét nào trên máy chủ.'), findsOneWidget);
  });

  testWidgets('Displays connection error and retry button when network fails', (tester) async {
    final mockClient = MockClient((request) async =>
        throw http.ClientException('Failed to connect'));

    final api = DamageApi(client: mockClient);

    await tester.pumpWidget(
      MaterialApp(
        home: HistoryScreen(damageApi: api),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Không thể kết nối máy chủ'), findsOneWidget);
    expect(find.text('Thử lại'), findsOneWidget);
  });
}
