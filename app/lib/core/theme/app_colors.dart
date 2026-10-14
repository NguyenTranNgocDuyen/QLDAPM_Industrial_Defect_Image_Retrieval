import 'package:flutter/material.dart';

abstract class AppColors {
  // Dark neutral lab canvas & surfaces
  static const Color darkCanvas = Color(0xFF101216);
  static const Color darkSurface = Color(0xFF181B20);
  static const Color darkSurfaceElevated = Color(0xFF22262C);
  static const Color darkBorder = Color(0xFF2C323B);
  static const Color darkBorderSubtle = Color(0xFF1F242B);

  // Light neutral for inspection reports/history
  static const Color lightCanvas = Color(0xFFF4F5F7);
  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightBorder = Color(0xFFDDE1E6);
  static const Color lightTextPrimary = Color(0xFF15181E);
  static const Color lightTextSecondary = Color(0xFF5A6370);

  // Text tokens (Dark mode)
  static const Color textPrimaryDark = Color(0xFFF1F3F5);
  static const Color textSecondaryDark = Color(0xFF8C96A5);
  static const Color textMutedDark = Color(0xFF5A6370);

  // Primary Accent: Industrial Amber
  static const Color amberAccent = Color(0xFFF59E0B);
  static const Color amberMuted = Color(0x33F59E0B);
  static const Color amberDark = Color(0xFFD97706);

  // Sensor & QC states
  static const Color statusPass = Color(0xFF10B981);
  static const Color statusWarning = Color(0xFFF59E0B);
  static const Color statusFail = Color(0xFFEF4444);

  // Defect severity tokens (Colorblind safe + High contrast)
  static const Color defectMinor = Color(0xFF10B981);     // Nhẹ: Xanh ngọc
  static const Color defectModerate = Color(0xFFF59E0B);  // Trung bình: Hổ phách
  static const Color defectCritical = Color(0xFFEF4444);  // Nghiêm trọng: Đỏ san hô
}
