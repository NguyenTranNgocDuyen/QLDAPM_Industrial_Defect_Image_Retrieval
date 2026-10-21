import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

enum PhotoReviewAction { keep, retake }

class PhotoReviewScreen extends StatelessWidget {
  final String sideLabel;
  final Uint8List imageBytes;
  final bool isFromGallery;

  const PhotoReviewScreen({
    super.key,
    required this.sideLabel,
    required this.imageBytes,
    this.isFromGallery = false,
  });

  @override
  Widget build(BuildContext context) {
    final retakeLabel = isFromGallery ? 'Chọn lại' : 'Chụp lại';
    final semanticLabel = isFromGallery
        ? 'Ảnh $sideLabel từ thư viện'
        : 'Ảnh $sideLabel vừa chụp';

    return Scaffold(
      backgroundColor: AppColors.darkCanvas,
      appBar: AppBar(title: Text('Xem lại · $sideLabel')),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ClipRect(
                child: InteractiveViewer(
                  minScale: 1,
                  maxScale: 5,
                  child: SizedBox.expand(
                    child: Image.memory(
                      imageBytes,
                      key: const ValueKey('review-photo'),
                      fit: BoxFit.contain,
                      semanticLabel: semanticLabel,
                      errorBuilder: (_, _, _) => Center(
                        child: Text(
                          isFromGallery
                              ? 'Không xem được ảnh đã chọn. Hãy chọn lại.'
                              : 'Không xem được ảnh. Hãy chụp lại.',
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Chụm hai ngón tay để phóng to và kiểm tra độ nét.',
                    textAlign: TextAlign.center,
                    style: AppTypography.bodyMedium,
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          key: const ValueKey('review-retake'),
                          onPressed: () =>
                              Navigator.pop(context, PhotoReviewAction.retake),
                          icon: Icon(
                            isFromGallery
                                ? Icons.photo_library_outlined
                                : Icons.replay,
                          ),
                          label: Text(retakeLabel),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: FilledButton.icon(
                          key: const ValueKey('review-keep'),
                          onPressed: () =>
                              Navigator.pop(context, PhotoReviewAction.keep),
                          icon: const Icon(Icons.check),
                          label: const Text('Giữ ảnh này'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
