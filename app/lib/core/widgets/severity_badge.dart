import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../theme/defect_theme_ext.dart';
import '../../features/inspection/models/defect_item.dart';

class SeverityBadge extends StatelessWidget {
  final DefectSeverity severity;
  final bool showSymbol;
  final bool compact;

  const SeverityBadge({
    super.key,
    required this.severity,
    this.showSymbol = true,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    final defectExt = Theme.of(context).extension<DefectThemeExtension>();

    final Color badgeColor;
    switch (severity) {
      case DefectSeverity.minor:
        badgeColor = defectExt?.minorDefect ?? AppColors.defectMinor;
        break;
      case DefectSeverity.moderate:
        badgeColor = defectExt?.moderateDefect ?? AppColors.defectModerate;
        break;
      case DefectSeverity.critical:
        badgeColor = defectExt?.criticalDefect ?? AppColors.defectCritical;
        break;
    }

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 6 : 8,
        vertical: compact ? 2 : 4,
      ),
      decoration: BoxDecoration(
        color: badgeColor.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: badgeColor.withValues(alpha: 0.85), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showSymbol) ...[
            Text(
              severity.symbol,
              style: TextStyle(
                fontSize: compact ? 9 : 11,
                color: badgeColor,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(width: 4),
          ],
          Text(
            severity.label.toUpperCase(),
            style: AppTypography.monoSmall.copyWith(
              color: badgeColor,
              fontWeight: FontWeight.w700,
              fontSize: compact ? 9 : 10,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }
}
