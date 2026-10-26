import csv, io, json, sys
from pathlib import Path
import numpy as np, pytest
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from preprocessing.enhancement import equalize_luminance
from preprocessing.filtering import gaussian_filter, median_filter
from preprocessing.histogram import save_histogram
from preprocessing.resize import letterbox_resize, source_to_letterbox, letterbox_to_source
from defect_vision.image_io import decode_upright_rgb
from defect_vision.preprocess_benchmark import PRESETS, run as run_benchmark
from preprocessing.experiment import create_experiment
from scripts.validate_manifest import validate

@pytest.mark.parametrize("fn,args",[(gaussian_filter,{"kernel_size":4}), (gaussian_filter,{"sigma":0}), (median_filter,{"kernel_size":2})])
def test_filter_validation(fn,args):
    with pytest.raises(ValueError): fn(np.zeros((8,8),np.uint8),**args)
def test_filters_and_enhancement_preserve_alpha():
    image=np.dstack((np.full((20,30,3),100,np.uint8),np.full((20,30),77,np.uint8)))
    for fn in (gaussian_filter,median_filter,equalize_luminance):
        output=fn(image); assert output.shape==image.shape and output.dtype==np.uint8
        np.testing.assert_array_equal(output[...,3],image[...,3])
def _artifact_dir(name):
    path=Path('tv1-test-artifacts')/name; path.mkdir(parents=True,exist_ok=True); return path

def test_histogram_and_letterbox_mapping():
    output=_artifact_dir('histogram'); image=np.zeros((10,20,3),np.uint8); data=save_histogram(image,output/'hist.png')
    assert (output/'hist.png').is_file() and (output/'hist.json').is_file() and sum(data['blue'])==200
    _,meta=letterbox_resize(Image.fromarray(image),(101,101)); point=(19.2,9.3)
    restored=letterbox_to_source(*source_to_letterbox(*point,meta),meta)
    assert max(abs(a-b) for a,b in zip(point,restored)) <= 1
    from preprocessing.resize import map_bbox_to_letterbox, map_bbox_to_source
    box=(1.25, 2.5, 18.75, 8.5)
    assert map_bbox_to_source(map_bbox_to_letterbox(box,meta),meta) == pytest.approx(box)

def test_experiment_and_offline_benchmark_artifacts():
    output=_artifact_dir('experiment-benchmark'); source=output/'input.png'; Image.new('RGB',(32,20),(40,90,180)).save(source)
    experiment=output/'experiment'; create_experiment(source,experiment,32)
    expected={'original.png','resized.png','gaussian.png','median.png','contrast_enhanced.png',
              'histogram_original.png','histogram_original.json','histogram_enhanced.png',
              'histogram_enhanced.json','comparison.png'}
    assert {item.name for item in experiment.iterdir()} == expected
    rows=run_benchmark([source],output/'benchmark',list(PRESETS))
    assert len(rows)==len(PRESETS) and {row['preset'] for row in rows} == set(PRESETS)
    report=json.loads((output/'benchmark'/'report.json').read_text(encoding='utf-8'))
    assert len(report['rows']) == len(PRESETS) and all(Path(row['output']).is_file() for row in rows)

def test_manifest_validator_detects_leakage_hash_and_dimensions():
    output=_artifact_dir('manifest'); image=output/'image.png'; damage=output/'damage.png'; body=output/'body.png'
    Image.new('RGB',(12,10)).save(image); Image.new('L',(12,10)).save(damage); Image.new('L',(12,10)).save(body)
    import hashlib
    fields=['source','license','image_path','damage_mask_path','body_mask_path','annotation_id','group_id','split','sha256']
    row=dict(zip(fields,['local','test-license',str(image),str(damage),str(body),'a1','device-1','test',hashlib.sha256(image.read_bytes()).hexdigest()]))
    manifest=output/'manifest.csv'
    with manifest.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields); writer.writeheader(); writer.writerow(row)
    assert validate(manifest) == []
    row['split']='train'
    with manifest.open('a',newline='',encoding='utf-8') as stream: csv.DictWriter(stream,fieldnames=fields).writerow(row)
    assert any('group leakage' in error for error in validate(manifest))
@pytest.mark.parametrize("orientation,shape",[(3,(20,30)),(6,(30,20)),(8,(30,20))])
def test_decode_orientation_and_modes(orientation,shape):
    stream=io.BytesIO(); exif=Image.Exif(); exif[274]=orientation
    Image.new("RGB",(30,20),(1,2,3)).save(stream,"JPEG",exif=exif); assert decode_upright_rgb(stream.getvalue()).shape==(shape[0],shape[1],3)
def test_decode_grayscale_rgba_corrupt_and_guard():
    for image in (Image.new("L",(4,3)),Image.new("RGBA",(4,3))):
        stream=io.BytesIO(); image.save(stream,"PNG"); assert decode_upright_rgb(stream.getvalue()).shape==(3,4,3)
    with pytest.raises(ValueError): decode_upright_rgb(b"not an image")
    stream=io.BytesIO(); Image.new("RGB",(11,10)).save(stream,"PNG")
    with pytest.raises(ValueError): decode_upright_rgb(stream.getvalue(),max_pixels=100)
