# Visual Defect Detection — TV1

TV1 provides a binary CNN classifier for electronic-device images:

`image → preprocessing → CNN → normal / defective`

It deliberately does **not** locate scratches, cracks, or dents. That is TV2's YOLO responsibility.

## Install

The repository already contains a directory named `requirements.txt`, so TV1 dependencies are at `requirements.txt/tv1.txt`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt\tv1.txt
```

## Dataset layout

Place actual images (not the `.gitkeep` placeholders) in this exact layout. Use image-level labels: an intact device is `normal`; an image containing visible exterior damage is `defective`.

```text
data/
  train/{normal,defective}/
  val/{normal,defective}/
  test/{normal,defective}/
```

Keep the test split untouched until the final evaluation. A practical starting split is 70% / 15% / 15%, with balanced classes where possible.

## Preprocessing experiment

Create images and histogram figures for the report before deciding the final pipeline:

```powershell
python -m preprocessing.experiment path\to\sample.jpg --output-dir outputs\preprocessing_experiment
```

Default training uses `Resize(224×224) + Normalize`. Compare it with one filter or contrast enhancement at a time:

```powershell
python -m model.train --filter-name gaussian
python -m model.train --filter-name median
python -m model.train --contrast-enhancement
```

Each run writes `outputs/model/defect_classifier.pt` and `training_history.json`. Record each run's test metrics in the report comparison table.

## Train, evaluate, and run UI

```powershell
python -m model.train --epochs 20
python -m model.evaluate
streamlit run ui\app.py
```

Evaluation writes accuracy, precision, recall, F1, a classification report, the confusion matrix, and the number of defective images incorrectly classified as normal (false negatives) to `outputs/evaluation/`.
