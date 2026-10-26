"""Offline A/B preprocessing benchmark; deliberately never calls v3 inference."""
from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path
from time import perf_counter
import cv2, numpy as np
from .illumination import correct_illumination
from .image_io import read_image, write_image

PRESETS = ("raw", "gaussian", "median", "clahe", "gamma", "background", "combined")
def run(inputs: list[Path], output: Path, presets: list[str]) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True); rows=[]
    config={"version":"offline-preprocess-ab-v1","presets":presets}; digest=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    for path in inputs:
        image=read_image(path, cv2.IMREAD_COLOR)
        if image is None: raise ValueError(f"Cannot decode {path}")
        for preset in presets:
            started=perf_counter()
            if preset == "raw": value=image.copy(); params={}
            elif preset == "gaussian": value=cv2.GaussianBlur(image,(5,5),1); params={"kernel":5,"sigma":1}
            elif preset == "median": value=cv2.medianBlur(image,3); params={"kernel":3}
            else:
                result=correct_illumination(image, preset); value=result.image; params=result.parameters
            elapsed=(perf_counter()-started)*1000; artifact=output/f"{path.stem}_{preset}.png"; write_image(artifact,value)
            rows.append({"input":str(path),"preset":preset,"parameters":json.dumps(params,sort_keys=True),"preprocess_latency_ms":round(elapsed,3),"output":str(artifact),"config_sha256":digest,"warning":"Image-quality metrics are not model-quality metrics; this result cannot justify changing model input."})
    (output/"report.json").write_text(json.dumps({"config":config,"rows":rows},indent=2),encoding="utf-8")
    with (output/"report.csv").open("w",newline="",encoding="utf-8") as stream: csv.DictWriter(stream,fieldnames=rows[0].keys()).writeheader(); csv.DictWriter(stream,fieldnames=rows[0].keys()).writerows(rows)
    return rows
if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("inputs",nargs="+"); parser.add_argument("--output-dir",default="outputs/preprocess-benchmark"); parser.add_argument("--presets",nargs="+",choices=PRESETS,default=list(PRESETS)); args=parser.parse_args()
    run([Path(p) for p in args.inputs],Path(args.output_dir),args.presets)
