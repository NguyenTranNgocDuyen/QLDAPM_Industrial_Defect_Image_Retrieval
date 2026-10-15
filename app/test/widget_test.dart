import 'package:flutter_test/flutter_test.dart';
import 'package:cosmetic_inspector/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const CosmeticInspectorApp());
    expect(find.textContaining('SN/IMEI'), findsOneWidget);
  });
}
