import 'package:flutter/material.dart';
import 'app_colors.dart';
import 'app_dimens.dart';
import 'app_typography.dart';
import 'defect_theme_ext.dart';

class AppTheme {
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.darkCanvas,
      canvasColor: AppColors.darkCanvas,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.amberAccent,
        surface: AppColors.darkSurface,
        onSurface: AppColors.textPrimaryDark,
      ),
      extensions: const [DefectThemeExtension.dark],
      appBarTheme: AppBarTheme(
        backgroundColor: AppColors.darkCanvas,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: AppTypography.titleMedium,
        iconTheme: const IconThemeData(color: AppColors.textPrimaryDark),
      ),
      cardTheme: CardThemeData(
        color: AppColors.darkSurface,
        shape: RoundedRectangleBorder(
          borderRadius: AppDimens.borderSm,
          side: const BorderSide(color: AppColors.darkBorder, width: AppDimens.borderWidth),
        ),
        elevation: 0,
        margin: EdgeInsets.zero,
      ),
      dividerTheme: const DividerThemeData(
        color: AppColors.darkBorderSubtle,
        thickness: 1,
        space: 1,
      ),
    );
  }

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: AppColors.lightCanvas,
      canvasColor: AppColors.lightCanvas,
      colorScheme: const ColorScheme.light(
        primary: AppColors.amberDark,
        surface: AppColors.lightSurface,
        onSurface: AppColors.lightTextPrimary,
      ),
      extensions: const [DefectThemeExtension.light],
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.lightSurface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: AppColors.lightSurface,
        shape: RoundedRectangleBorder(
          borderRadius: AppDimens.borderSm,
          side: const BorderSide(color: AppColors.lightBorder, width: AppDimens.borderWidth),
        ),
        elevation: 0,
        margin: EdgeInsets.zero,
      ),
    );
  }
}
