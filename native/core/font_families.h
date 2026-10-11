// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef CAMOUFLOW_NATIVE_CORE_FONT_FAMILIES_H_
#define CAMOUFLOW_NATIVE_CORE_FONT_FAMILIES_H_

#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace camouflow::native {

inline std::string FontFamilyKey(std::string_view name) {
  std::string key(name);
  for (char& character : key) {
    if (character >= 'A' && character <= 'Z')
      character = static_cast<char>(character + ('a' - 'A'));
  }
  return key;
}

// This Windows-only pilot accepts exact printable ASCII family names. Arial
// must be present so Blink can load an actual last-resort font without crashing.
inline std::optional<std::vector<std::string>> ParseFontFamilies(
    std::string_view value) {
  if (value.empty() || value.size() > 4096)
    return std::nullopt;
  std::vector<std::string> families;
  std::vector<std::string> keys;
  bool has_arial = false;
  while (!value.empty()) {
    const auto separator = value.find(',');
    const auto name = value.substr(0, separator);
    if (name.empty() || name.size() > 128 || name.front() == ' ' ||
        name.back() == ' ' || families.size() == 64)
      return std::nullopt;
    for (const unsigned char character : name) {
      if (character < 0x20 || character > 0x7e || character == '"' ||
          character == '\\' || character == ';')
        return std::nullopt;
    }
    const auto key = FontFamilyKey(name);
    for (const auto& previous : keys) {
      if (previous == key)
        return std::nullopt;
    }
    has_arial = has_arial || key == "arial";
    families.emplace_back(name);
    keys.push_back(key);
    if (separator == std::string_view::npos)
      break;
    value.remove_prefix(separator + 1);
    if (value.empty())
      return std::nullopt;
  }
  return has_arial ? std::optional(std::move(families)) : std::nullopt;
}

}  // namespace camouflow::native
#endif  // CAMOUFLOW_NATIVE_CORE_FONT_FAMILIES_H_
