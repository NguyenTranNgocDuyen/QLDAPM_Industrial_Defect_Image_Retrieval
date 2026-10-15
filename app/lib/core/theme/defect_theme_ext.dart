import 'package:flutter/material.dart';
import 'app_colors.dart';

class DefectThemeExtension extends ThemeExtension<DefectThemeExtension> {
  final Color minorDefect;
  final Color moderateDefect;
  final Color criticalDefect;
  final Color overlayGrid;

  const DefectThemeExtension({
    required this.minorDefect,
    required this.moderateDefect,
    required this.criticalDefect,
    required this.overlayGrid,
  });

  @override
  DefectThemeExtension copyWith({
    Color? minorDefect,
    Color? moderateDefect,
    Color? criticalDefect,
    Color? overlayGrid,
  }) {
    return DefectThemeExtension(
      minorDefect: minorDefect ?? this.minorDefect,
      moderateDefect: moderateDefect ?? this.moderateDefect,
      criticalDefect: criticalDefect ?? this.criticalDefect,
      overlayGrid: overlayGrid ?? this.overlayGrid,
    );
  }

  @override
  DefectThemeExtension lerp(ThemeExtension<DefectThemeExtension>? other, double t) {
    if (other is! DefectThemeExtension) return this;
    return DefectThemeExtension(
      minorDefect: Color.lerp(minorDefect, other.minorDefect, t)!,
      moderateDefect: Color.lerp(moderateDefect, other.moderateDefect, t)!,
      criticalDefect: Color.lerp(criticalDefect, other.criticalDefect, t)!,
      overlayGrid: Color.lerp(overlayGrid, other.overlayGrid, t)!,
    );
  }

  static const dark = DefectThemeExtension(
    minorDefect: AppColors.defectMinor,
    moderateDefect: AppColors.defectModerate,
    criticalDefect: AppColors.defectCritical,
    overlayGrid: Color(0x22F59E0B),
  );

  static const light = DefectThemeExtension(
    minorDefect: AppColors.defectMinor,
    moderateDefect: AppColors.defectModerate,
    criticalDefect: AppColors.defectCritical,
    overlayGrid: Color(0x1815181E),
  );
}
