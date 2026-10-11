// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "core/hardware_limits.h"
#include "core/font_families.h"

#ifdef _WIN32
#include "windows/font_collection.h"
#endif

#include <iostream>
#include <string_view>

int main() {
  using camouflow::native::HardwareLimitsError;
  using camouflow::native::ParseHardwareLimits;
  unsigned failures = 0;
  const auto check = [&failures](bool passed, std::string_view name) {
    if (!passed) {
      std::cerr << "Failed: " << name << '\n';
      ++failures;
    }
  };

  using camouflow::native::ParseFontFamilies;
  const auto families = ParseFontFamilies("Arial,Times New Roman,Segoe UI");
  check(families && families->size() == 3, "exact genuine family policy");
  for (const auto value : {"", "Segoe UI", "Arial,", ",Arial", "Arial,,Segoe UI",
                           "Arial,arial", "Arial, Segoe UI", "Arial ",
                           "Arial\n", "Arial;Segoe UI", "Arial,\"Segoe UI\""}) {
    check(!ParseFontFamilies(value), "invalid family policy rejected atomically");
  }
  check(ParseFontFamilies("arial").has_value(), "case-insensitive Arial requirement");
  check(!ParseFontFamilies("Arial," + std::string(129, 'x')), "family length bound");
  check(!ParseFontFamilies(std::string(4097, 'x')), "policy length bound");
  std::string many_families = "Arial";
  for (unsigned i = 0; i < 64; ++i)
    many_families += ",Family" + std::to_string(i);
  check(!ParseFontFamilies(many_families), "family count bound");

#ifdef _WIN32
  using Microsoft::WRL::ComPtr;
  ComPtr<IDWriteFactory3> factory;
  auto hr = DWriteCreateFactory(DWRITE_FACTORY_TYPE_ISOLATED,
                                __uuidof(IDWriteFactory3),
                                reinterpret_cast<IUnknown**>(factory.GetAddressOf()));
  check(SUCCEEDED(hr) && factory, "actual Windows DirectWrite factory");
  if (!factory)
    return 1;
  ComPtr<IDWriteFontCollection> system;
  hr = factory->GetSystemFontCollection(&system);
  check(SUCCEEDED(hr) && system, "actual Windows font collection");
  if (!system)
    return 1;
  ComPtr<IDWriteFontCollection> restricted;
  hr = camouflow::native::RestrictFontCollection(factory.Get(), system.Get(),
                                               {"Arial"}, &restricted);
  check(SUCCEEDED(hr) && restricted, "actual restricted native collection");
  if (!restricted)
    return 1;
  check(restricted->GetFontFamilyCount() == 1, "only selected native family remains");
  UINT32 original_index = 0;
  BOOL exists = FALSE;
  system->FindFamilyName(L"Arial", &original_index, &exists);
  check(exists, "real Arial exists on host");
  UINT32 masked_index = 0;
  restricted->FindFamilyName(L"Times New Roman", &masked_index, &exists);
  check(!exists, "non-selected host family not exposed");
  ComPtr<IDWriteFontFamily> original_family;
  ComPtr<IDWriteFontFamily> masked_family;
  system->GetFontFamily(original_index, &original_family);
  restricted->GetFontFamily(0, &masked_family);
  check(original_family && masked_family, "genuine family retained");
  if (!original_family || !masked_family)
    return 1;
  check(original_family->GetFontCount() == masked_family->GetFontCount(),
        "all original family styles retained");
  ComPtr<IDWriteFont> original_font;
  ComPtr<IDWriteFont> masked_font;
  original_family->GetFirstMatchingFont(DWRITE_FONT_WEIGHT_NORMAL,
      DWRITE_FONT_STRETCH_NORMAL, DWRITE_FONT_STYLE_NORMAL, &original_font);
  masked_family->GetFirstMatchingFont(DWRITE_FONT_WEIGHT_NORMAL,
      DWRITE_FONT_STRETCH_NORMAL, DWRITE_FONT_STYLE_NORMAL, &masked_font);
  check(original_font && masked_font, "actual matching font style");
  if (!original_font || !masked_font)
    return 1;
  DWRITE_FONT_METRICS original_metrics{};
  DWRITE_FONT_METRICS masked_metrics{};
  original_font->GetMetrics(&original_metrics);
  masked_font->GetMetrics(&masked_metrics);
  check(original_metrics.designUnitsPerEm == masked_metrics.designUnitsPerEm &&
        original_metrics.ascent == masked_metrics.ascent &&
        original_metrics.descent == masked_metrics.descent &&
        original_metrics.capHeight == masked_metrics.capHeight &&
        original_metrics.xHeight == masked_metrics.xHeight,
        "native font metrics unchanged");
  ComPtr<IDWriteFontFallback> fallback;
  hr = camouflow::native::CreateRestrictedFontFallback(factory.Get(),
      restricted.Get(), {"Arial"}, &fallback);
  check(SUCCEEDED(hr) && fallback, "restricted glyph fallback built natively");
  ComPtr<IDWriteFontCollection> invalid;
  hr = camouflow::native::RestrictFontCollection(factory.Get(), system.Get(),
      {"Arial", "CamouFlow Missing Fixture Font 890731"}, &invalid);
  check(hr == DWRITE_E_NOFONT && !invalid,
        "missing requested fonts rejected without system fallback");
#endif

  auto result = ParseHardwareLimits("", "");
  check(static_cast<bool>(result), "explicit native defaults");
  check(result.limits.ReportedConcurrency(12) == 12, "unconfigured concurrency");
  check(result.limits.ReportedMemory(16.0f) == 16.0f, "unconfigured memory");

  result = ParseHardwareLimits("4", "2");
  check(static_cast<bool>(result), "supported limits");
  check(result.limits.ReportedConcurrency(12) == 4, "concurrency limit");
  check(result.limits.ReportedConcurrency(2) == 2, "cannot invent processors");
  check(result.limits.ReportedMemory(16.0f) == 2.0f, "memory limit");
  check(result.limits.ReportedMemory(0.5f) == 0.5f, "cannot invent memory");

  for (auto value : {"0", "65", "-1", "+4", "4.0", " 4", "4 ", "4x", "true", "999999999999999999999999"}) {
    check(ParseHardwareLimits(value, "").error == HardwareLimitsError::kInvalidConcurrency,
          "invalid concurrency rejected");
  }
  for (auto value : {"0", "0.1", "3", "32", "nan", "inf", "4.0", " 4", "4x"}) {
    check(ParseHardwareLimits("", value).error == HardwareLimitsError::kInvalidMemory,
          "invalid memory rejected");
  }
  for (auto value : {"0.25", "0.5", "1", "2", "4", "8", "16"}) {
    check(static_cast<bool>(ParseHardwareLimits("64", value)), "supported memory bucket");
  }
  check(!static_cast<bool>(ParseHardwareLimits("4", "invalid")), "partial configuration is not success");
  check(!ParseHardwareLimits("4", "invalid").limits.concurrency.has_value(), "invalid configuration is atomic");
  return failures == 0 ? 0 : 1;
}
