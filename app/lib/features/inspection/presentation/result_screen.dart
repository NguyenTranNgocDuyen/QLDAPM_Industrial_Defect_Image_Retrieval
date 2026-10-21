import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../data/damage_api.dart';
import '../data/gallery_saver_service.dart';
import '../models/capture_condition.dart';
import 'history_screen.dart';

const _reasonLabels = {
  'geometry_or_target_aspect_unconfirmed':
      'Hình học mặt quan sát chưa đủ tin cậy.',
  'surface_occluded_cropped_or_unconfirmed':
      'Mặt có dấu hiệu che/cắt hoặc chưa đánh giá được đầy đủ.',
  'phone_touches_source_border':
      'Mask điện thoại chạm biên ảnh; có thể bị cắt.',
  'multiple_phones_need_target_confirmation':
      'Có nhiều điện thoại; cần xác nhận máy mục tiêu.',
  'surface_not_a_confirmed_planar_face':
      'Bề mặt chưa được xác nhận là một mặt phẳng.',
  'below_alarm_threshold':
      'Có ứng viên nhưng dưới ngưỡng báo ảnh 200 pixel gốc; cần kiểm tra.',
  'phone_not_found': 'Không phát hiện điện thoại; cần chụp lại hoặc kiểm tra.',
  'missing_surface_corners': 'Không xác định được bốn góc đáng tin cậy.',
  'invalid_surface_geometry': 'Chưa thể nắn phối cảnh ổn định; dùng phần nhìn thấy trên ảnh gốc.',
  'processing_error': 'Xử lý thất bại; không đủ dữ liệu để kết luận.',
  'connection_or_processing_error':
      'Không nhận được kết quả hợp lệ. Kiểm tra kết nối và máy chủ rồi thử lại.',
  'empty_visible_surface': 'Không có mask bề mặt quan sát hợp lệ.',
  'body_outside_quad': 'Bốn góc chưa bao phủ đủ mask điện thoại.',
  'surface_shape_incomplete':
      'Bề mặt không đủ gần hình chữ nhật để đo đáng tin cậy.',
  'surface_concave_or_occluded': 'Mask có vùng lõm hoặc dấu hiệu bị che khuất.',
  'perspective_too_oblique': 'Góc chụp quá xiên để ước tính hình học ổn định.',
  'surface_too_small': 'Mặt điện thoại trong ảnh quá nhỏ để đo.',
  'no_candidates_on_observed_surface':
      'Không phát hiện ứng viên trong mặt quan sát; không kết luận toàn máy lành.',
  'partial_area_estimate_only':
      'Mức sơ bộ chỉ dựa trên diện tích phần nhìn thấy; chưa đủ các số đo của mặt quan sát.',
  'visible_surface_too_small_for_estimate':
      'Vùng điện thoại nhận diện quá nhỏ để ước tính.',
  'area_width_confirmed_severe':
      'Diện tích và bề rộng cùng đạt ngưỡng Nặng.',
  'area_within_minor_limit':
      'Diện tích ứng viên trong ngưỡng Nhẹ; bề rộng và skeleton không tự nâng mức.',
  'width_requires_area_confirmation':
      'Bề rộng cao nhưng diện tích chưa đạt ngưỡng Nặng; giữ mức Vừa.',
  'area_requires_width_confirmation':
      'Diện tích cao nhưng bề rộng chưa đạt ngưỡng Nặng; giữ mức Vừa.',
  'severe_unconfirmed_without_width':
      'Chưa đo được bề rộng để xác nhận Nặng; mức sơ bộ tối đa Vừa, thực tế có thể cao hơn.',
};
const _levels = {'minor': 'Nhẹ', 'moderate': 'Vừa', 'severe': 'Nặng'};
const _locations = {
  'top_left': 'Trên trái',
  'top_center': 'Trên giữa',
  'top_right': 'Trên phải',
  'middle_left': 'Giữa trái',
  'middle_center': 'Trung tâm',
  'middle_right': 'Giữa phải',
  'bottom_left': 'Dưới trái',
  'bottom_center': 'Dưới giữa',
  'bottom_right': 'Dưới phải',
};

String describeReason(String reason) {
  if (_reasonLabels.containsKey(reason)) return _reasonLabels[reason]!;
  final parts = reason.split(':');
  final metric = {
    'area_ratio': 'Tỷ lệ diện tích',
    'skeleton_length_ratio': 'Chiều dài skeleton tương đối',
    'width_ratio': 'Độ dày mask tương đối',
  }[parts.first];
  if (metric != null && parts.length == 2) {
    return '$metric mức ${_levels[parts[1]] ?? parts[1]}.';
  }
  return reason;
}

class ResultScreen extends StatefulWidget {
  final String deviceName;
  final String deviceImei;
  final Map<InspectionStepType, Map<String, dynamic>> results;
  final Map<String, dynamic>? singleScanResult;
  final GallerySaverService gallerySaver;
  final DamageApi? damageApi;

  const ResultScreen({
    super.key,
    required this.deviceName,
    this.deviceImei = '',
    this.results = const {},
    this.singleScanResult,
    this.gallerySaver = const GalGallerySaverService(),
    this.damageApi,
  });

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  late final DamageApi _api;
  bool _overlay = true;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _api = widget.damageApi ?? DamageApi();
  }

  @override
  void dispose() {
    if (widget.damageApi == null) {
      _api.close();
    }
    super.dispose();
  }

  String _ratio(dynamic value) =>
      value is num ? '${(value * 100).toStringAsFixed(3)}%' : 'Chưa đủ dữ liệu';

  Future<void> _saveAsset({
    required String url,
    required String sideLabel,
    required String imageType,
    required String scanId,
  }) async {
    if (_isSaving) return;
    setState(() => _isSaving = true);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Row(
          children: [
            SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            SizedBox(width: 12),
            Text('Đang tải ảnh từ máy chủ...'),
          ],
        ),
        duration: Duration(seconds: 2),
      ),
    );
    try {
      final bytes = await _api.downloadAssetBytes(url);
      final shortId = scanId.length >= 8 ? scanId.substring(0, 8) : 'scan';
      final cleanSide = sideLabel.replaceAll(RegExp(r'\s+'), '_');
      final fileName = 'scan_${shortId}_${cleanSide}_$imageType';

      await widget.gallerySaver.saveImageBytes(
        bytes: bytes,
        fileName: fileName,
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppColors.statusPass,
          content: Text('Đã lưu vào thư viện ảnh'),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusFail,
          content: Text(e.toString()),
          action: SnackBarAction(
            label: 'Thử lại',
            textColor: Colors.white,
            onPressed: () => _saveAsset(
              url: url,
              sideLabel: sideLabel,
              imageType: imageType,
              scanId: scanId,
            ),
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  void _showSaveOptions(BuildContext context, String sideLabel, Map<String, dynamic> result) {
    final assets = (result['assets'] as Map?) ?? const {};
    final scanId = (result['scanId'] ?? '').toString();
    final sourceUrl = assets['source'] as String?;
    final overlayUrl = assets['overlay'] as String?;

    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.darkSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                child: Text(
                  'Lưu ảnh · $sideLabel',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ),
              const Divider(color: AppColors.darkBorder),
              ListTile(
                key: const ValueKey('save-source-option'),
                leading: const Icon(Icons.image_outlined, color: AppColors.amberAccent),
                title: const Text('Ảnh nguồn (gốc)'),
                subtitle: Text(
                  sourceUrl != null
                      ? 'Ảnh gốc độ phân giải đầy đủ, chuẩn hóa EXIF'
                      : 'Không có ảnh nguồn cho bản ghi này',
                  style: TextStyle(
                    color: sourceUrl != null
                        ? AppColors.textSecondaryDark
                        : AppColors.textMutedDark,
                  ),
                ),
                enabled: sourceUrl != null && !_isSaving,
                onTap: () {
                  Navigator.pop(sheetContext);
                  _saveAsset(
                    url: sourceUrl!,
                    sideLabel: sideLabel,
                    imageType: 'source',
                    scanId: scanId,
                  );
                },
              ),
              ListTile(
                key: const ValueKey('save-overlay-option'),
                leading: const Icon(Icons.layers_outlined, color: AppColors.amberAccent),
                title: const Text('Ảnh có vùng đánh dấu (overlay)'),
                subtitle: Text(
                  overlayUrl != null
                      ? 'Ảnh kèm lớp phủ trực quan vùng ứng viên hư hại'
                      : 'Không có ảnh đánh dấu (chưa phát hiện hư hại hoặc xử lý thất bại)',
                  style: TextStyle(
                    color: overlayUrl != null
                        ? AppColors.textSecondaryDark
                        : AppColors.textMutedDark,
                  ),
                ),
                enabled: overlayUrl != null && !_isSaving,
                onTap: () {
                  Navigator.pop(sheetContext);
                  _saveAsset(
                    url: overlayUrl!,
                    sideLabel: sideLabel,
                    imageType: 'overlay',
                    scanId: scanId,
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final single = widget.singleScanResult;
    final hasData = single != null || widget.results.isNotEmpty;

    return Scaffold(
      backgroundColor: AppColors.darkCanvas,
      appBar: AppBar(
        title: Text(widget.deviceName),
        actions: [
          IconButton(
            tooltip: _overlay ? 'Ẩn lớp phủ ứng viên' : 'Hiện lớp phủ ứng viên',
            icon: Icon(_overlay ? Icons.layers : Icons.layers_clear),
            onPressed: () => setState(() => _overlay = !_overlay),
          ),
          IconButton(
            key: const ValueKey('result-open-history'),
            tooltip: 'Lịch sử quét',
            icon: const Icon(Icons.history),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const HistoryScreen()),
              );
            },
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Mức độ hư hại ước tính',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
          ),
          if (!hasData)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'Không đủ dữ liệu. Hãy chụp ảnh và thực hiện phân tích.',
              ),
            ),
          if (single != null)
            _surfaceCard(
              _labelForSurface(single['damage']?['observed_surface'] as String?),
              single,
              sideKey: 'single',
            )
          else
            for (final entry in widget.results.entries)
              _surfaceCard(
                entry.key.label,
                entry.value,
                sideKey: entry.key.name,
              ),
        ],
      ),
    );
  }

  String _labelForSurface(String? surface) {
    switch (surface?.toLowerCase()) {
      case 'front':
        return 'Mặt trước';
      case 'back':
        return 'Mặt sau';
      default:
        return 'Mặt quan sát';
    }
  }

  Widget _surfaceCard(String sideLabel, Map<String, dynamic> result, {required String sideKey}) {
    final severity = (result['severity'] as Map?) ?? const {};
    final damage = (result['damage'] as Map?) ?? const {};
    final assets = (result['assets'] as Map?) ?? const {};
    final image = _overlay
        ? assets['overlay'] ?? assets['display']
        : assets['display'];
    final level = _levels[severity['estimated_severity']];
    final needsReview = severity['needs_review'] != false;
    final imageEstimate =
        severity['status'] == 'estimated' &&
        severity['estimation_basis'] == 'image_geometry';
    final partialEstimate = severity['estimation_basis'] == 'observed_area_only';
    final areaLedRule = severity['classification_rule'] == 'area_led_width_confirmation';
    final areaWidthRule = areaLedRule || severity['classification_rule'] == 'area_and_width';
    final label = level != null
        ? '$level${partialEstimate
              ? ' · Sơ bộ trên phần nhìn thấy'
              : imageEstimate
              ? ' · Ước tính theo ảnh'
              : needsReview
              ? ' · Cần kiểm tra'
              : ''}'
        : (severity['status'] == 'no_detected_damage'
              ? 'Chưa phát hiện ứng viên trên mặt quan sát'
              : 'Cần kiểm tra / Không đủ dữ liệu');

    return Card(
      margin: const EdgeInsets.only(top: 20),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    sideLabel,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                OutlinedButton.icon(
                  key: ValueKey('save-image-btn-$sideKey'),
                  onPressed: _isSaving ? null : () => _showSaveOptions(context, sideLabel, result),
                  icon: const Icon(Icons.download_outlined, size: 16),
                  label: const Text('Lưu ảnh'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Mức độ hư hại ước tính: $label',
              style: const TextStyle(color: AppColors.amberAccent),
            ),
            if (areaWidthRule)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  areaLedRule
                      ? 'Diện tích quyết định mức Nhẹ/Vừa theo ngưỡng cấu hình. Mức Nặng cần cả diện tích và bề rộng đạt ngưỡng. Skeleton chỉ tham khảo; số pixel không quyết định mức độ. Ngưỡng thử nghiệm chưa kiểm chứng.'
                      : 'Mức Nặng cần diện tích và bề rộng cùng đạt ngưỡng cấu hình. Skeleton chỉ tham khảo; số pixel không quyết định mức độ. Ngưỡng thử nghiệm chưa kiểm chứng.',
                ),
              ),
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text(
                'Vùng tô màu là ứng viên do model đề xuất, chưa phải hư hại đã được xác nhận. Model có thể nhận nhầm phản chiếu, đường viền hoặc chi tiết hình ảnh.',
              ),
            ),
            if (partialEstimate)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  'Ảnh thiếu phần hoặc hình học chưa đủ tin cậy. Chỉ ước tính theo diện tích vùng nhìn thấy trên ảnh gốc; chưa chấm chiều dài/độ dày và phần không xuất hiện trong ảnh. Đây không phải mức độ của toàn mặt hoặc toàn máy.',
                ),
              ),
            if (((severity['limitations'] as List?) ?? const [])
                .contains('target_automatically_selected'))
              const Text(
                'Có nhiều điện thoại; đang đánh giá máy được detector chọn. Hãy kiểm tra vùng đánh dấu đúng máy cần xem.',
              ),
            if (result['error'] is Map && result['error']['message'] is String)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(result['error']['message'] as String),
              ),
            if (image is String)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: SizedBox(
                  height: 300,
                  width: double.infinity,
                  child: InteractiveViewer(
                    maxScale: 6,
                    child: Image.network(
                      DamageApi.assetUrl(image),
                      fit: BoxFit.contain,
                      errorBuilder: (_, _, _) => const Center(
                        child: Text('Không tải được ảnh kết quả.'),
                      ),
                    ),
                  ),
                ),
              ),
            if (severity['locations'] is List &&
                (severity['locations'] as List).isNotEmpty)
              Text(
                '${partialEstimate ? 'Vị trí trên ảnh gốc' : 'Phân bố khu vực hư hại'}: ${(severity['locations'] as List).map((item) => _locations[item['region']] ?? item['region']).join(', ')}',
              ),
            Text(
              'Diện tích ứng viên / mặt quan sát: ${_ratio(severity['area_ratio'])}',
            ),
            Text(
              'Skeleton lớn nhất / đường chéo mặt${areaWidthRule ? ' (tham khảo)' : ''}: ${_ratio(severity['skeleton_length_ratio'])}',
            ),
            Text(
              'Bề rộng P90 lớn nhất / cạnh ngắn mặt: ${_ratio(severity['width_ratio'])}',
            ),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: const Text('Thông tin phát hiện (không dùng để phân cấp)'),
              children: [
                Text(
                  'Pixel ứng viên ở ảnh gốc: ${damage['candidate_pixels_original'] ?? 'Chưa đủ dữ liệu'}',
                ),
                Text(
                  'Báo ảnh (≥ 200 pixel gốc): ${damage['found'] == null
                      ? 'Chưa đủ dữ liệu'
                      : damage['found'] == true
                      ? 'Có'
                      : 'Chưa đạt'}',
                ),
              ],
            ),
            const SizedBox(height: 8),
            for (final reason in (severity['reasons'] as List?) ?? const [])
              Text('• ${describeReason(reason.toString())}'),
            const SizedBox(height: 8),
            Text(
              'Cấu hình: ${severity['config_version'] ?? 'Chưa có'} · Chưa kiểm chứng',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
