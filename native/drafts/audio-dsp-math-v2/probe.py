# Copyright 2026 CamouFlow contributors.
# SPDX-License-Identifier: MIT
"""Pinned Windows DSP workbench. No browser/runtime admission is granted."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

EXPECTED_SOURCES = {'148/third_party/blink/renderer/platform/audio/dynamics_compressor.cc': 'ddcfdaf4c750614ae852c85926d659a1f242c5c154a23a4daaac2f6c3f35e99d',
 '148/third_party/blink/renderer/platform/audio/dynamics_compressor.h': '39da7be02ca6198c4d36da959625aa9873580d9c064fbdecca75793324489f82',
 '156/third_party/blink/renderer/platform/audio/audio_utilities.cc': '904354af32f9724dc59fe6621759c013fe24006056975fce086e53a23269a498',
 '156/third_party/blink/renderer/platform/audio/dynamics_compressor.cc': '14f1ac7ee487ba94d6f244b0efbad5c27c7cbf36ea9aa7abdeab7bf1f1f6e86a',
 '156/third_party/blink/renderer/platform/audio/dynamics_compressor.h': '3db6b7dce689adf832d2f5d6cfe2f0feff1e814138cbd3b2c3ebe37b4e865576',
 '156/third_party/fdlibm/ieee754.cc': '661b229dd99d262594df7a25d1c709d63f0af202c9bae252b3cabbaeb27d7d2f',
 '156/third_party/fdlibm/ieee754.h': '67ac025f301eb38f63a4523f94f0cc30a4c0aa2f441f40f6e139026a84d49072'}


def verify(args: argparse.Namespace) -> dict:
    SOURCE = args.source_156.resolve(strict=True)
    LEGACY = args.source_148.resolve(strict=True)
    ROOT = args.output.resolve()
    if os.name != "nt" or ROOT.drive.upper() != "D:":
        raise ValueError("This Windows workbench requires a fresh output directory on D:")
    if ROOT.exists() or ROOT.is_relative_to(SOURCE) or ROOT.is_relative_to(LEGACY):
        raise ValueError("Output must be a new directory outside both checkouts")
    for path in (SOURCE, LEGACY, ROOT, args.vs_installation.resolve(), args.fdlibm_object.resolve()):
        if any(character in str(path) for character in '%!\r\n"'):
            raise ValueError("Build paths contain unsupported batch characters")
    for name, expected in EXPECTED_SOURCES.items():
        label, relative = name.split("/", 1)
        base = SOURCE if label == "156" else LEGACY
        if hashlib.sha256((base / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("Pinned source mismatch: " + name)
    ROOT.mkdir(parents=True)
    audio = 'third_party/blink/renderer/platform/audio/'
    owned = Path(__file__).with_name('compressor_math_policy.h')
    policy_bytes = owned.read_bytes()
    (ROOT / owned.name).write_bytes(policy_bytes)
    fdlibm = args.fdlibm_object.resolve(strict=True)
    obj_bytes = fdlibm.read_bytes()
    if obj_bytes[:2] != b'\x64\x86':
        raise ValueError("The supplied fdlibm object must be x64 COFF")
    (ROOT / 'fdlibm.obj').write_bytes(obj_bytes)
    header = ROOT / 'third_party/fdlibm/ieee754.h'
    header.parent.mkdir(parents=True)
    header.write_bytes((SOURCE / 'third_party/fdlibm/ieee754.h').read_bytes())
    hashes = {}

    def read(root, name, label):
        body = (root / name).read_bytes()
        hashes[label + '/' + name] = hashlib.sha256(body).hexdigest()
        return body.decode('utf-8-sig')

    def function(text, name):
        start = text.index(name)
        opening = text.index('{', start)
        end, depth = opening + 1, 1
        while depth:
            depth += (text[end] == '{') - (text[end] == '}')
            end += 1
        return text[start:end] + '\n'

    read(SOURCE, 'third_party/fdlibm/ieee754.cc', '156')
    read(SOURCE, 'third_party/fdlibm/ieee754.h', '156')
    utilities = read(SOURCE, audio + 'audio_utilities.cc', '156')
    functions = ''.join(function(utilities, signature) for signature in (
        'float DecibelsToLinear(', 'float LinearToDecibels(', 'double DiscreteTimeConstantForSampleRate('))
    adapters = r'''
    #pragma once
    #include <algorithm>
    #include <array>
    #include <cmath>
    #include <cstdlib>
    #include <memory>
    #include <span>
    #include <vector>
    inline float GlintPrototypeClamp(float value, float min, float max) {
      if (value >= max) return max;
      return value <= min ? min : value;
    }
    #include "third_party/fdlibm/ieee754.h"
    #include "compressor_math_policy.h"
    #define PLATFORM_EXPORT
    #define USING_FAST_MALLOC(Type)
    #define DCHECK(value) do { if (!(value)) std::abort(); } while (0)
    #define CHECK_EQ(a,b) DCHECK((a) == (b))
    #define DCHECK_EQ(a,b) CHECK_EQ(a,b)
    #define DCHECK_GE(a,b) DCHECK((a) >= (b))
    #define DCHECK_LT(a,b) DCHECK((a) < (b))
    namespace blink {
    inline float ClampTo(float value, float min, float max) {
      return GlintPrototypeClamp(value, min, max);
    }
    constexpr float kPiOverTwoFloat = static_cast<float>(1.57079632679489661923);
    template<class T> using Vector = std::vector<T>;
    class AudioFloatArray {
     public:
      explicit AudioFloatArray(size_t size) : values_(size) {}
      void Zero() { std::fill(values_.begin(), values_.end(), 0.f); }
      float& at(size_t index) { return values_.at(index); }
     private: std::vector<float> values_;
    };
    class AudioChannel {
     public:
      explicit AudioChannel(size_t size) : values_(size) {}
      std::span<const float> Span() const { return values_; }
      std::span<float> MutableSpan() { return values_; }
     private: std::vector<float> values_;
    };
    class AudioBus {
     public:
      AudioBus(unsigned count, size_t size) { for (unsigned i=0;i<count;++i) channels_.emplace_back(size); }
      unsigned NumberOfChannels() const { return static_cast<unsigned>(channels_.size()); }
      AudioChannel* Channel(unsigned index) { return &channels_.at(index); }
      const AudioChannel* Channel(unsigned index) const { return &channels_.at(index); }
     private: std::vector<AudioChannel> channels_;
    };
    class DenormalDisabler {
     public: static float FlushDenormalFloatToZero(float value) { return value; }
    };
    namespace audio_utilities {
    '''
    adapters += ('float DecibelsToLinear(float);\nfloat LinearToDecibels(float);\n'
                 'double DiscreteTimeConstantForSampleRate(double, double);\n}\n}\n')
    notice = utilities[:utilities.index('#include')]
    (ROOT / 'utilities.cc').write_text(notice + '#include "adapters.h"\nnamespace blink::audio_utilities {\n'
                                      + functions + '\n}\n', encoding='utf-8', newline='\n')
    (ROOT / 'adapters.h').write_text(adapters, encoding='utf-8', newline='\n')
    replacement_counts = {}
    for label, root, cls in (('156', SOURCE, 'DynamicsCompressor'), ('148', LEGACY, 'LegacyDynamicsCompressor')):
        h = read(root, audio + 'dynamics_compressor.h', label)
        cc = read(root, audio + 'dynamics_compressor.cc', label)
        h = re.sub(r'^#include .*\n', '', h, flags=re.M)
        h = h.replace('#define THIRD_PARTY_BLINK_RENDERER_PLATFORM_AUDIO_DYNAMICS_COMPRESSOR_H_',
                      '#define THIRD_PARTY_BLINK_RENDERER_PLATFORM_AUDIO_DYNAMICS_COMPRESSOR_H_\n#include "adapters.h"', 1)
        needle = 'DynamicsCompressor(float sample_rate, unsigned number_of_channels);'
        assert h.count(needle) == 1
        h = h.replace(needle, 'DynamicsCompressor(float sample_rate, unsigned number_of_channels,\n'
                      '                     glint::candidate::CompressorMathPolicy math_policy);', 1)
        needle = '  unsigned number_of_channels_;'
        assert h.count(needle) == 1
        h = h.replace(needle, '  const glint::candidate::CompressorMathPolicy math_policy_;\n' + needle, 1)
        cc = re.sub(r'^#include .*\n', '', cc, flags=re.M)
        cc = '#include "' + cls + '.h"\n' + cc
        needle = 'unsigned number_of_channels)\n    : number_of_channels_'
        assert cc.count(needle) == 1
        cc = cc.replace(needle, 'unsigned number_of_channels,\n'
                        '                                       glint::candidate::CompressorMathPolicy math_policy)\n'
                        '    : math_policy_(math_policy), number_of_channels_', 1)
        replacements = [('fdlibm::powf(', 'math_policy_.Pow(', 2),
                        ('fdlibm::asinf(', 'math_policy_.Asin(', 1),
                        ('sin(static_cast<double>(', 'math_policy_.Sin(static_cast<double>(', 1),
                        ('exp(static_cast<double>(', 'math_policy_.Exp(static_cast<double>(', 1)]
        replacement_counts[label] = {}
        for old, new, count in replacements:
            assert cc.count(old) == count
            replacement_counts[label][old] = count
            cc = cc.replace(old, new)
        if cls != 'DynamicsCompressor':
            h = h.replace('THIRD_PARTY_BLINK_RENDERER_PLATFORM_AUDIO_DYNAMICS_COMPRESSOR_H_', 'GLINT_LEGACY_DYNAMICS_COMPRESSOR_H_')
            h = h.replace('DynamicsCompressor', cls)
            cc = cc.replace('DynamicsCompressor', cls).replace('LegacyLegacyDynamicsCompressor.h', 'LegacyDynamicsCompressor.h')
        (ROOT / (cls + '.h')).write_text(h, encoding='utf-8', newline='\n')
        (ROOT / (cls + '.cc')).write_text(cc, encoding='utf-8', newline='\n')
    driver = Path(__file__).with_name('driver.cc')
    (ROOT / driver.name).write_bytes(driver.read_bytes())
    CLANG = SOURCE / 'third_party/llvm-build/Release+Asserts/bin/clang-cl.exe'
    developer = args.vs_installation.resolve(strict=True) / 'Common7/Tools/VsDevCmd.bat'
    if not CLANG.is_file() or not developer.is_file():
        raise ValueError("Explicit Clang/Visual Studio developer tools are required")
    report = {'schema': 1, 'scope': 'Copied pinned compressor algorithms; not browser runtime or device emulation',
              'compiled_browser': False, 'runtime_verified': False, 'production_admitted': False,
              'variant_compatibility_admitted': False,
              'measurement_complete': False, 'reference_browser_calibration_required': True,
              'source_sha256': hashes, 'policy_sha256': hashlib.sha256(policy_bytes).hexdigest(),
              'driver_sha256': hashlib.sha256(driver.read_bytes()).hexdigest(),
              'compiler_sha256': hashlib.sha256(CLANG.read_bytes()).hexdigest(),
              'fdlibm_object_sha256': hashlib.sha256(obj_bytes).hexdigest(),
              'callsite_replacements': replacement_counts}
    try:
        temporary = ROOT / 'tmp'
        temporary.mkdir()
        batch = ROOT / 'compile.cmd'
        command = (f'"{CLANG}" /nologo /std:c++20 /EHsc /MT /O2 /fp:strict /W4 /WX '
                   '/clang:-ffp-contract=off /clang:-fmsc-version=1950 '
                   f'/I"{ROOT}" "{ROOT / "driver.cc"}" "{ROOT / "DynamicsCompressor.cc"}" '
                   f'"{ROOT / "LegacyDynamicsCompressor.cc"}" "{ROOT / "utilities.cc"}" "{ROOT / "fdlibm.obj"}" '
                   f'/Fe:"{ROOT / "probe.exe"}"')
        batch.write_text('@echo off\ncall "' + str(developer) + '" -arch=x64 -host_arch=x64\n'
                         'if errorlevel 1 exit /b 1\n' + command + '\nexit /b %errorlevel%\n', encoding='utf-8')
        with (ROOT / 'compile.log').open('wb') as log:
            subprocess.run(['cmd.exe', '/d', '/c', str(batch)], cwd=ROOT, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=120,
                           env={**os.environ, 'TMP': str(temporary), 'TEMP': str(temporary)})
        output = subprocess.run([str(ROOT / 'probe.exe')], cwd=ROOT, capture_output=True,
                                text=True, check=True, timeout=60)
        report['prototype'] = json.loads(output.stdout)
        report['pow_special_value_parity'] = report['prototype']['pow_edge_category_mismatches'] == 0
        report['measurement_complete'] = True
    finally:
        report['source_inputs_unchanged'] = all(
            hashlib.sha256(((SOURCE if name.startswith('156/') else LEGACY) / name.split('/', 1)[1]).read_bytes()).hexdigest() == digest
            for name, digest in hashes.items())
        report['policy_unchanged'] = owned.read_bytes() == policy_bytes
        report['fdlibm_object_unchanged'] = fdlibm.read_bytes() == obj_bytes
        report['driver_unchanged'] = hashlib.sha256(driver.read_bytes()).hexdigest() == report['driver_sha256']
        report['compiler_unchanged'] = hashlib.sha256(CLANG.read_bytes()).hexdigest() == report['compiler_sha256']
        (ROOT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    if not all(report[key] for key in ('source_inputs_unchanged', 'policy_unchanged', 'fdlibm_object_unchanged', 'driver_unchanged', 'compiler_unchanged')):
        raise ValueError("An experiment input changed during the probe")
    metrics = report['prototype']
    if any(metrics[name] != 0 for name in ('legacy_native_different_samples', 'segmentation_differences', 'interleaved_differences')):
        raise ValueError("The isolated DSP invariants failed; inspect retained report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-156", type=Path, required=True)
    parser.add_argument("--source-148", type=Path, required=True)
    parser.add_argument("--fdlibm-object", type=Path, required=True)
    parser.add_argument("--vs-installation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify(args)
    except (OSError, ValueError, AssertionError, subprocess.SubprocessError) as error:
        print(f"DSP experiment failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
