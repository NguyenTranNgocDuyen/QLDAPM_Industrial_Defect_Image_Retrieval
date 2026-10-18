# TV1 dependencies

`requirements.txt` was already a directory in this repository, therefore the
installable dependency file is [tv1.txt](tv1.txt). From the repository root:

```bash
python -m pip install -r requirements.txt/tv1.txt
```

For a CPU-only PyTorch environment, follow the PyTorch wheel selector if the
default `torch` install selects a CUDA build that is unsuitable for the host.
