# TV1 evaluation requirements

Preprocessing artifacts measure image appearance only; they do not establish model quality or authorize changing the v3 input. Phone v3 continues to infer on raw, EXIF-upright, source-resolution RGB.

Use an independent, reproducible test split and report segmentation IoU, Dice, pixel precision/recall, image-level precision/recall/F1, specificity, FPR, plus warm and cold latency on the demo machine. ROC-AUC requires continuous scores. A normal/defective classifier report is valid only when an independent binary classifier and probability score exist.

`scripts/validate_manifest.py` expects CSV columns: `source,license,image_path,damage_mask_path,body_mask_path,annotation_id,group_id,split,sha256`. It rejects missing files/hashes, mismatched masks, missing test data, and group leakage across splits. No model may be called evaluation-ready without that independent test report.
