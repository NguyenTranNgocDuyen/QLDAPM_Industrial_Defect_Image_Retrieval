import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../../features/inspection/models/capture_condition.dart';

class QualityIndicatorHUD extends StatelessWidget {
  final CaptureCondition condition;

  const QualityIndicatorHUD({super.key, required this.condition});

  Color _stateColor(QualityState state) {
    switch (state) {
      case QualityState.pass:
        return AppColors.statusPass;
      case QualityState.warning:
        return AppColors.statusWarning;
      case QualityState.fail:
        return AppColors.statusFail;
    }
  }

  Widget _buildPill({
    required String label,
    required String value,
    required QualityState state,
  }) {
    final color = _stateColor(state);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.darkSurface.withValues(alpha: 0.85),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.8), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 5),
          Text(
            '$label: ',
            style: AppTypography.monoSmall.copyWith(color: AppColors.textSecondaryDark),
          ),
          Text(
            value,
            style: AppTypography.monoSmall.copyWith(
              color: AppColors.textPrimaryDark,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        _buildPill(
          label: 'ỔN ĐỊNH',
          value: '${(condition.stability * 100).toInt()}%',
          state: condition.stabilityState,
        ),
        _buildPill(
          label: 'QUANG THÔNG',
          value: '${condition.lightingLux.toInt()} lx',
          state: condition.lightState,
        ),
        _buildPill(
          label: 'ĐỘ LÓA',
          value: condition.glareState == QualityState.pass ? 'TỐT' : 'CHÓI LÓA',
          state: condition.glareState,
        ),
      ],
    );
  }
}
