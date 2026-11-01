"""Check bounded Canvas backing/PNG observations; no policy admission."""

from pathlib import Path
import re
import runpy


TEXT = runpy.run_path(str(Path(__file__).with_name('validate.py')))


def validate(observed):
    if (not isinstance(observed, dict) or type(observed.get('schema')) is not int
            or observed['schema'] != 1 or type(observed.get('passed')) is not bool):
        raise ValueError('Expected a versioned expanded rendering observation')
    rows = observed.get('rows')
    if (not isinstance(rows, list) or len(rows) != len(TEXT['CONTEXTS'])
            or any(not isinstance(row, dict) for row in rows)
            or [row.get('name') for row in rows] != list(TEXT['CONTEXTS'])):
        raise ValueError('Expanded rendering context coverage is incomplete')
    complete = True
    for row in rows:
        if type(row.get('passed')) is not bool:
            raise ValueError('Expanded context verdict must be explicit')
        if 'error' in row:
            if row['passed'] or not isinstance(row['error'], str) or not row['error']:
                raise ValueError('Invalid expanded context failure')
            complete = False
            continue
        variants = row.get('variants')
        if (not isinstance(variants, list) or len(variants) != 2
                or any(not isinstance(v, dict) or type(v.get('willReadFrequently')) is not bool
                       for v in variants)
                or [v['willReadFrequently'] for v in variants] != [False, True]):
            raise ValueError('Both ordered backing requests are required')
        for variant in variants:
            count = variant.get('multicolourChangedChannels')
            if type(count) is not int or not 0 <= count <= 256:
                raise ValueError('Invalid multicolour changed-channel count')
            # Reuse the strict text/image validator; exports are checked below.
            images = variant.get('images')
            text_row = dict(name=row['name'], images=images,
                            plainChangedChannels=variant.get('plainChangedChannels'))
            text_row['passed'] = (text_row['plainChangedChannels'] == 0
                and isinstance(images, list) and all(isinstance(i, dict)
                    and i.get('repeatExact') is True for i in images))
            text_rows = [{**text_row, 'name': name} for name in TEXT['CONTEXTS']]
            TEXT['validate'](dict(schema=1, rows=text_rows, passed=text_row['passed']))
            export_passed = True
            expected_names = (['toDataURL', 'toBlob']
                if row['name'] in ('document-html', 'same-origin-frame') else ['convertToBlob'])
            for image in images:
                exports = image.get('exports')
                if (not isinstance(exports, list) or len(exports) != len(expected_names)
                        or any(not isinstance(e, dict) for e in exports)
                        or [e.get('name') for e in exports] != expected_names):
                    raise ValueError('PNG export coverage is incomplete or reordered')
                for export in exports:
                    changed, digest = export.get('changedChannels'), export.get('sha256')
                    if (type(changed) is not int or not 0 <= changed <= 192 * 96 * 4
                            or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)):
                        raise ValueError('Invalid PNG digest or changed-channel count')
                    if (changed == 0) != (digest == image['sha256']):
                        raise ValueError('PNG exact verdict contradicts its digest')
                    export_passed = export_passed and changed == 0
            passed = text_row['passed'] and count == 0 and export_passed
            if type(variant.get('passed')) is not bool or variant['passed'] != passed:
                raise ValueError('Expanded variant verdict contradicts measurements')
        if row['passed'] != all(v['passed'] for v in variants):
            raise ValueError('Expanded context verdict contradicts its variants')
    passed = complete and all(row['passed'] for row in rows)
    if observed['passed'] != passed:
        raise ValueError('Expanded combined verdict contradicts its contexts')
    return dict(measurement_complete=complete, passed=passed, contexts=len(rows),
                privacy_admitted=False, production_admitted=False)
