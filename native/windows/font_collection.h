// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef CAMOUFLOW_NATIVE_WINDOWS_FONT_COLLECTION_H_
#define CAMOUFLOW_NATIVE_WINDOWS_FONT_COLLECTION_H_

#include <dwrite_3.h>
#include <wrl/client.h>

#include <string>
#include <vector>

namespace camouflow::native {

inline HRESULT RestrictFontCollection(
    IDWriteFactory3* factory,
    IDWriteFontCollection* source,
    const std::vector<std::string>& names,
    IDWriteFontCollection** destination) {
  if (!destination)
    return E_INVALIDARG;
  *destination = nullptr;
  if (!factory || !source || names.empty())
    return E_INVALIDARG;
  Microsoft::WRL::ComPtr<IDWriteFontSetBuilder> builder;
  HRESULT result = factory->CreateFontSetBuilder(&builder);
  if (FAILED(result))
    return result;
  for (const auto& name : names) {
    const std::wstring wide(name.begin(), name.end());
    UINT32 index = 0;
    BOOL exists = FALSE;
    result = source->FindFamilyName(wide.c_str(), &index, &exists);
    if (FAILED(result))
      return result;
    if (!exists)
      return DWRITE_E_NOFONT;
    Microsoft::WRL::ComPtr<IDWriteFontFamily> family;
    result = source->GetFontFamily(index, &family);
    if (FAILED(result))
      return result;
    if (!family->GetFontCount())
      return DWRITE_E_NOFONT;
    for (UINT32 face_index = 0; face_index < family->GetFontCount(); ++face_index) {
      Microsoft::WRL::ComPtr<IDWriteFont> font;
      result = family->GetFont(face_index, &font);
      if (FAILED(result))
        return result;
      Microsoft::WRL::ComPtr<IDWriteFont3> font3;
      result = font.As(&font3);
      if (FAILED(result))
        return result;
      Microsoft::WRL::ComPtr<IDWriteFontFaceReference> reference;
      result = font3->GetFontFaceReference(&reference);
      if (FAILED(result))
        return result;
      result = builder->AddFontFaceReference(reference.Get());
      if (FAILED(result))
        return result;
    }
  }
  Microsoft::WRL::ComPtr<IDWriteFontSet> set;
  result = builder->CreateFontSet(&set);
  if (FAILED(result))
    return result;
  Microsoft::WRL::ComPtr<IDWriteFontCollection1> collection;
  result = factory->CreateFontCollectionFromFontSet(set.Get(), &collection);
  if (FAILED(result))
    return result;
  return collection.CopyTo(destination);
}

inline HRESULT CreateRestrictedFontFallback(
    IDWriteFactory2* factory,
    IDWriteFontCollection* collection,
    const std::vector<std::string>& names,
    IDWriteFontFallback** destination) {
  if (!destination)
    return E_INVALIDARG;
  *destination = nullptr;
  if (!factory || !collection || names.empty())
    return E_INVALIDARG;
  Microsoft::WRL::ComPtr<IDWriteFontFallbackBuilder> builder;
  HRESULT result = factory->CreateFontFallbackBuilder(&builder);
  if (FAILED(result))
    return result;
  std::vector<std::wstring> wide_names;
  wide_names.reserve(names.size());
  for (const auto& name : names)
    wide_names.emplace_back(name.begin(), name.end());
  std::vector<const wchar_t*> pointers;
  for (const auto& name : wide_names)
    pointers.push_back(name.c_str());
  const DWRITE_UNICODE_RANGE range = {0, 0x10ffff};
  result = builder->AddMapping(&range, 1, pointers.data(),
                               static_cast<UINT32>(pointers.size()),
                               collection, nullptr, nullptr, 1.0f);
  if (FAILED(result))
    return result;
  return builder->CreateFontFallback(destination);
}

}  // namespace camouflow::native
#endif  // CAMOUFLOW_NATIVE_WINDOWS_FONT_COLLECTION_H_
