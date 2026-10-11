// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef CAMOUFLOW_NATIVE_WINDOWS_FONT_CONFIGURATION_H_
#define CAMOUFLOW_NATIVE_WINDOWS_FONT_CONFIGURATION_H_

#include "base/check.h"
#include "base/command_line.h"
#include "ui/gfx/win/camouflow_font_collection.h"
#include "ui/gfx/win/camouflow_font_families.h"

namespace camouflow::native {

inline const std::optional<std::vector<std::string>>& GetFontFamilies() {
  static const auto families = []() -> std::optional<std::vector<std::string>> {
    const auto* command = base::CommandLine::ForCurrentProcess();
    constexpr char kSwitch[] = "camouflow-font-families";
    if (!command->HasSwitch(kSwitch))
      return std::nullopt;
    const auto parsed = ParseFontFamilies(command->GetSwitchValueASCII(kSwitch));
    CHECK(parsed) << "Invalid CamouFlow Native font families";
    return parsed;
  }();
  return families;
}

inline Microsoft::WRL::ComPtr<IDWriteFontCollection> ApplyFontFamilies(
    IDWriteFactory3* factory,
    Microsoft::WRL::ComPtr<IDWriteFontCollection> source) {
  const auto& families = GetFontFamilies();
  if (!families)
    return source;
  Microsoft::WRL::ComPtr<IDWriteFontCollection> restricted;
  const HRESULT result = RestrictFontCollection(factory, source.Get(),
                                               *families, &restricted);
  CHECK(SUCCEEDED(result) && restricted)
      << "Unavailable CamouFlow Native font family collection";
  return restricted;
}

inline Microsoft::WRL::ComPtr<IDWriteFontFallback> GetRestrictedFontFallback(
    IDWriteFactory2* factory,
    IDWriteFontCollection* collection) {
  const auto& families = GetFontFamilies();
  CHECK(families);
  Microsoft::WRL::ComPtr<IDWriteFontFallback> fallback;
  const HRESULT result = CreateRestrictedFontFallback(factory, collection,
                                                      *families, &fallback);
  CHECK(SUCCEEDED(result) && fallback)
      << "Unavailable CamouFlow Native font fallback";
  return fallback;
}

}  // namespace camouflow::native
#endif  // CAMOUFLOW_NATIVE_WINDOWS_FONT_CONFIGURATION_H_
