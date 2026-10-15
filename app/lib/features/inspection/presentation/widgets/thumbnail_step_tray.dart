import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_typography.dart';
import '../../models/capture_condition.dart';

class StepThumbnailTray extends StatelessWidget {
  final List<InspectionStepType> steps;
  final int activeIndex;
  final Map<int, String> capturedThumbnails;
  final ValueChanged<int> onStepSelected;

  const StepThumbnailTray({
    super.key,
    required this.steps,
    required this.activeIndex,
    required this.capturedThumbnails,
    required this.onStepSelected,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 72,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: steps.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final isCurrent = index == activeIndex;
          final isDone = capturedThumbnails.containsKey(index);
          final step = steps[index];

          return GestureDetector(
            onTap: () => onStepSelected(index),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 150),
              width: 60,
              decoration: BoxDecoration(
                color: isCurrent ? AppColors.darkSurfaceElevated : AppColors.darkSurface,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                  color: isCurrent
                      ? AppColors.amberAccent
                      : (isDone ? AppColors.statusPass : AppColors.darkBorder),
                  width: isCurrent ? 1.5 : 1.0,
                ),
              ),
              child: Stack(
                children: [
                  Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          isDone ? Icons.check_circle_outline : Icons.crop_free,
                          size: 18,
                          color: isDone
                              ? AppColors.statusPass
                              : (isCurrent ? AppColors.amberAccent : AppColors.textSecondaryDark),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${index + 1}/${steps.length}',
                          style: AppTypography.monoSmall.copyWith(
                            fontSize: 9,
                            color: isCurrent ? Colors.white : AppColors.textSecondaryDark,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Positioned(
                    bottom: 2,
                    left: 2,
                    right: 2,
                    child: Text(
                      step.label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 8, color: AppColors.textSecondaryDark),
                    ),
                  )
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
