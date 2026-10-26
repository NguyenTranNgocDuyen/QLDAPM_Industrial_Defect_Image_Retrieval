import 'dart:typed_data';

import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_typography.dart';
import '../../models/capture_condition.dart';

class StepThumbnailTray extends StatelessWidget {
  final List<InspectionStepType> steps;
  final int activeIndex;
  final Map<int, String> capturedThumbnails;
  final Map<int, Uint8List> thumbnailBytes;
  final ValueChanged<int> onStepSelected;

  const StepThumbnailTray({
    super.key,
    required this.steps,
    required this.activeIndex,
    required this.capturedThumbnails,
    this.thumbnailBytes = const {},
    required this.onStepSelected,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          for (var index = 0; index < steps.length; index++) ...[
            if (index > 0) const SizedBox(width: 12),
            Expanded(child: _buildStep(index)),
          ],
        ],
      ),
    );
  }

  Widget _buildStep(int index) {
    final isCurrent = index == activeIndex;
    final isDone = capturedThumbnails.containsKey(index);
    final step = steps[index];
    final color = isCurrent
        ? AppColors.amberAccent
        : (isDone ? AppColors.statusPass : AppColors.textSecondaryDark);

    return Semantics(
      button: true,
      selected: isCurrent,
      label: '${step.label}, ${isDone ? 'đã chụp' : 'chưa chụp'}',
      excludeSemantics: true,
      child: GestureDetector(
        onTap: () => onStepSelected(index),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          decoration: BoxDecoration(
            color: isCurrent
                ? AppColors.darkSurfaceElevated
                : AppColors.darkSurface,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: isCurrent || isDone ? color : AppColors.darkBorder,
              width: isCurrent ? 1.5 : 1,
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (thumbnailBytes[index] case final bytes?)
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: Image.memory(
                    bytes,
                    width: 48,
                    height: 48,
                    fit: BoxFit.cover,
                    cacheWidth: 144,
                    errorBuilder: (_, _, _) => Icon(
                      Icons.check_circle_outline,
                      size: 48,
                      color: color,
                    ),
                  ),
                )
              else
                Icon(
                  isDone
                      ? Icons.check_circle_outline
                      : (step == InspectionStepType.front
                            ? Icons.phone_android
                            : Icons.smartphone),
                  size: 48,
                  color: color,
                ),
              const SizedBox(height: 6),
              Text(
                step.label,
                textAlign: TextAlign.center,
                style: AppTypography.bodyMedium.copyWith(
                  fontWeight: FontWeight.w600,
                  color: isCurrent ? Colors.white : AppColors.textSecondaryDark,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                isDone ? 'Đã chụp' : 'Chưa chụp',
                textAlign: TextAlign.center,
                style: AppTypography.monoSmall.copyWith(color: color),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
