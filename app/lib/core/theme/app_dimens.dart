import 'package:flutter/material.dart';

abstract class AppDimens {
  static const double xs = 4.0;
  static const double sm = 8.0;
  static const double md = 12.0;
  static const double lg = 16.0;
  static const double xl = 24.0;
  static const double xxl = 32.0;

  static const Radius radiusXs = Radius.circular(3.0);
  static const Radius radiusSm = Radius.circular(6.0);
  static const Radius radiusMd = Radius.circular(8.0);
  static const Radius radiusLg = Radius.circular(12.0);

  static const BorderRadius borderSm = BorderRadius.all(radiusSm);
  static const BorderRadius borderMd = BorderRadius.all(radiusMd);
  static const BorderRadius borderLg = BorderRadius.all(radiusLg);

  static const double borderWidth = 1.0;
  static const double borderFocusWidth = 1.5;
}
