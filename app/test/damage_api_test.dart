import 'dart:async';
import 'dart:io';
import 'package:cosmetic_inspector/features/inspection/data/damage_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'Connection timeout fails before reading or uploading an image',
    () async {
      var calls = 0;
      final api = DamageApi(
        client: MockClient((request) async {
          calls++;
          expect(request.url.path, '/api/health');
          throw TimeoutException('No route');
        }),
      );
      addTearDown(api.close);
      await expectLater(
        api.analyze('/missing-photo.jpg', 'front'),
        throwsA(
          isA<DamageApiException>().having(
            (e) => e.code,
            'code',
            'connection_timeout',
          ),
        ),
      );
      expect(calls, 1);
    },
  );

  test(
    'Network errors are explicit instead of a generic processing result',
    () async {
      final api = DamageApi(
        client: MockClient(
          (_) async => throw http.ClientException('Connection refused'),
        ),
      );
      addTearDown(api.close);
      await expectLater(
        api.checkConnection(),
        throwsA(
          isA<DamageApiException>().having(
            (e) => e.code,
            'code',
            'connection_failed',
          ),
        ),
      );
    },
  );

  test('Wrong health endpoint does not proceed to upload', () async {
    final api = DamageApi(
      client: MockClient((_) async => http.Response('<html/>', 200)),
    );
    addTearDown(api.close);
    await expectLater(
      api.checkConnection(),
      throwsA(
        isA<DamageApiException>().having(
          (e) => e.code,
          'code',
          'invalid_backend',
        ),
      ),
    );
  });

  test(
    'Healthy backend receives original multipart bytes and returns results',
    () async {
      final dir = await Directory.systemTemp.createTemp('damage-api-test-');
      addTearDown(() => dir.delete(recursive: true));
      final image = await File(
        '${dir.path}/photo.jpg',
      ).writeAsBytes([1, 3, 5, 7]);
      final methods = <String>[];
      final api = DamageApi(
        client: MockClient((request) async {
          methods.add(request.method);
          if (request.method == 'GET') {
            return http.Response('{"status":"UP"}', 200);
          }
          expect(request.url.path, '/api/detections');
          expect(
            request.headers['content-type'],
            contains('multipart/form-data'),
          );
          expect(request.bodyBytes, containsAllInOrder([1, 3, 5, 7]));
          return http.Response(
            '{"severity":{"status":"estimated"},"damage":{"found":true}}',
            200,
          );
        }),
      );
      addTearDown(api.close);
      final result = await api.analyze(image.path, 'front');
      expect(methods, ['GET', 'POST']);
      expect(result['severity']['status'], 'estimated');
    },
  );

  test(
    'Backend HTTP failure and malformed results preserve error categories',
    () async {
      final dir = await Directory.systemTemp.createTemp(
        'damage-api-error-test-',
      );
      addTearDown(() => dir.delete(recursive: true));
      final image = await File('${dir.path}/photo.jpg').writeAsBytes([1]);
      for (final (status, body, code) in [
        (503, '{}', 'http_error'),
        (200, '[]', 'invalid_response'),
        (200, '{}', 'invalid_response'),
      ]) {
        final api = DamageApi(
          client: MockClient(
            (request) async => request.method == 'GET'
                ? http.Response('{"status":"UP"}', 200)
                : http.Response(body, status),
          ),
        );
        try {
          await expectLater(
            api.analyze(image.path, 'front'),
            throwsA(
              isA<DamageApiException>().having((e) => e.code, 'code', code),
            ),
          );
        } finally {
          api.close();
        }
      }
    },
  );

  test('normalizeBaseUrl correctly adds default port 8080 and handles formatting', () {
    expect(DamageApi.normalizeBaseUrl('http://10.251.63.27'), 'http://10.251.63.27:8080');
    expect(DamageApi.normalizeBaseUrl('http://10.251.63.27/'), 'http://10.251.63.27:8080');
    expect(DamageApi.normalizeBaseUrl('10.251.63.27'), 'http://10.251.63.27:8080');
    expect(DamageApi.normalizeBaseUrl('http://10.251.63.27:8080'), 'http://10.251.63.27:8080');
    expect(DamageApi.normalizeBaseUrl('http://localhost:9000'), 'http://localhost:9000');
    expect(DamageApi.normalizeBaseUrl('https://api.example.com'), 'https://api.example.com');
  });

  test('detectMimeAndFilename accurately recognizes WebP, PNG, JPEG', () {
    final webpBytes = [
      0x52, 0x49, 0x46, 0x46, 0, 0, 0, 0, 0x57, 0x45, 0x42, 0x50, 1, 2
    ];
    final pngBytes = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];
    final jpegBytes = [0xFF, 0xD8, 0xFF, 0xE0, 0, 0x10, 0x4A, 0x46];

    expect(DamageApi.detectMimeAndFilename('photo.webp', webpBytes), ('image/webp', 'photo.webp'));
    expect(DamageApi.detectMimeAndFilename('photo.png', pngBytes), ('image/png', 'photo.png'));
    expect(DamageApi.detectMimeAndFilename('photo.jpg', jpegBytes), ('image/jpeg', 'photo.jpg'));
  });
}
