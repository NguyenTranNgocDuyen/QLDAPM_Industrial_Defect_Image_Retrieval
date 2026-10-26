import 'package:cosmetic_inspector/features/inspection/models/capture_condition.dart';
import 'package:cosmetic_inspector/features/inspection/presentation/result_screen.dart';
import 'package:cosmetic_inspector/features/inspection/presentation/analysis_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Area-led rule shows minor and separates pixel diagnostics', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ResultScreen(
      deviceName: 'Phone', results: {InspectionStepType.back: {
        'severity': {
          'status': 'estimated', 'estimated_severity': 'minor', 'needs_review': true,
          'estimation_basis': 'image_geometry', 'classification_rule': 'area_led_width_confirmation',
          'area_ratio': 0.0066949, 'width_ratio': 0.031746, 'skeleton_length_ratio': 0.294,
          'reasons': ['area_within_minor_limit'],
        },
        'damage': {'candidate_pixels_original': 405, 'found': true},
      }},
    )));
    expect(find.text('Mức độ hư hại ước tính: Nhẹ · Ước tính theo ảnh'), findsOneWidget);
    expect(find.textContaining('Skeleton chỉ tham khảo; số pixel không quyết định mức độ'), findsOneWidget);
    expect(find.textContaining('Diện tích ứng viên trong ngưỡng Nhẹ'), findsOneWidget);
    expect(find.textContaining('Diện tích quyết định mức Nhẹ/Vừa'), findsOneWidget);
    expect(find.textContaining('chưa phải hư hại đã được xác nhận'), findsOneWidget);
    expect(find.text('Pixel ứng viên ở ảnh gốc: 405'), findsNothing);
    final diagnostics = find.text('Thông tin phát hiện (không dùng để phân cấp)');
    await tester.ensureVisible(diagnostics);
    await tester.tap(diagnostics);
    await tester.pumpAndSettle();
    expect(find.text('Pixel ứng viên ở ảnh gốc: 405'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Partial image estimate labels scope and unknown metrics', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ResultScreen(
      deviceName: 'Phone',
      results: {InspectionStepType.front: {
        'severity': {
          'status': 'estimated', 'estimated_severity': 'minor', 'needs_review': true,
          'estimation_basis': 'observed_area_only', 'severity_is_partial': true,
          'area_ratio': 0.001, 'skeleton_length_ratio': null, 'width_ratio': null,
          'reasons': ['partial_area_estimate_only'],
          'limitations': ['target_automatically_selected'],
        },
        'damage': {'found': true},
      }},
    )));
    expect(find.text('Mức độ hư hại ước tính: Nhẹ · Sơ bộ trên phần nhìn thấy'), findsOneWidget);
    expect(find.textContaining('chưa chấm chiều dài/độ dày'), findsOneWidget);
    expect(find.textContaining('chưa đủ các số đo của mặt quan sát'), findsOneWidget);
    expect(find.textContaining('Có nhiều điện thoại; đang đánh giá'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Analysis requires no phone model, size or visibility form', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: AnalysisScreen(
          deviceName: 'Phone',
          deviceImei: '',
          capturedImages: {InspectionStepType.front: '/photo.jpg'},
        ),
      ),
    );
    expect(find.byType(TextField), findsNothing);
    expect(find.byType(CheckboxListTile), findsNothing);
    expect(
      find.textContaining('Không cần nhập dòng máy hoặc kích thước'),
      findsOneWidget,
    );
    expect(find.text('Phân tích ảnh'), findsOneWidget);
  });

  testWidgets(
    'Image estimate shows severity and location without calibrated dimensions',
    (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: ResultScreen(
            deviceName: 'Phone',
            deviceImei: '',
            results: {
              InspectionStepType.front: {
                'severity': {
                  'status': 'estimated',
                  'estimated_severity': 'severe',
                  'needs_review': true,
                  'estimation_basis': 'image_geometry',
                  'locations': [
                    {'region': 'top_left', 'candidate_share': 0.6},
                    {'region': 'middle_center', 'candidate_share': 0.4},
                  ],
                  'reasons': ['area_ratio:severe'],
                },
                'damage': {'found': true},
              },
            },
          ),
        ),
      );
      expect(
        find.text('Mức độ hư hại ước tính: Nặng · Ước tính theo ảnh'),
        findsOneWidget,
      );
      expect(
        find.text('Phân bố khu vực hư hại: Trên trái, Trung tâm'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Displays geometric severity, ratios and independent alarm warning',
    (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: ResultScreen(
            deviceName: 'Phone',
            deviceImei: '',
            results: {
              InspectionStepType.front: {
                'severity': {
                  'estimated_severity': 'severe',
                  'needs_review': true,
                  'area_ratio': 0.0009,
                  'skeleton_length_ratio': 0.63,
                  'width_ratio': 0.002,
                  'config_version': 'geometry-v1-unvalidated',
                  'reasons': [
                    'skeleton_length_ratio:severe',
                    'below_alarm_threshold',
                  ],
                },
                'damage': {'candidate_pixels_original': 140, 'found': false},
              },
            },
          ),
        ),
      );
      expect(
        find.text('Mức độ hư hại ước tính: Nặng · Cần kiểm tra'),
        findsOneWidget,
      );
      expect(find.textContaining('63.000%'), findsOneWidget);
      expect(
        find.textContaining('200 pixel gốc; cần kiểm tra'),
        findsOneWidget,
      );
      expect(find.textContaining('Skeleton lớn nhất'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Processing errors never display a healthy or minor result', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: ResultScreen(
          deviceName: 'Phone',
          deviceImei: '',
          results: {
            InspectionStepType.back: {
              'error': {
                'code': 'connection_timeout',
                'message': 'Không kết nối được BE tại địa chỉ đã cấu hình.',
              },
              'severity': {
                'status': 'insufficient_evidence',
                'estimated_severity': null,
                'needs_review': true,
                'reasons': ['connection_or_processing_error'],
              },
              'damage': {'status': 'processing_error'},
            },
          },
        ),
      ),
    );
    expect(
      find.textContaining('Cần kiểm tra / Không đủ dữ liệu'),
      findsOneWidget,
    );
    expect(
      find.textContaining('Diện tích ứng viên / mặt quan sát: Chưa đủ dữ liệu'),
      findsOneWidget,
    );
    expect(find.textContaining('ước tính: Nhẹ'), findsNothing);
    expect(find.textContaining('Máy lành'), findsNothing);
    expect(tester.takeException(), isNull);
    expect(
      find.text('Không kết nối được BE tại địa chỉ đã cấu hình.'),
      findsOneWidget,
    );
  });
}
