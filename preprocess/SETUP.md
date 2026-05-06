# Setup (Windows, fresh install)

Tested with CUDA 13.1 driver, Python 3.12, torch 2.8.0+cu128.

## 1. Python 3.12

```powershell
winget install Python.Python.3.12
```

PyTorch has no wheels for Python 3.13+, so 3.12 is required.

## 2. PyTorch 2.8.0 with CUDA 12.8

```powershell
py -3.12 -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
```

CUDA 12.8 binaries work with CUDA 13.x drivers (backwards compatible). whisperx pins torch~=2.8.0 so the version must be exact.

## 3. whisperx

```powershell
py -3.12 -m pip install whisperx
```

## 4. onnxruntime-gpu

```powershell
py -3.12 -m pip uninstall onnxruntime -y
py -3.12 -m pip install --force-reinstall onnxruntime-gpu
```

CPU and GPU onnxruntime conflict — only keep the GPU version.

## 5. ffmpeg

```powershell
winget install ffmpeg
```

Restart the terminal after installing so PATH updates take effect.

## 6. Hugging Face login

1. Create an account at huggingface.co
2. Accept terms for both gated models:
   - https://huggingface.co/pyannote/speaker-diarization-community-1
   - https://huggingface.co/pyannote/segmentation-3.0
3. Create a read token at https://huggingface.co/settings/tokens
4. Log in:

```powershell
huggingface-cli login
```

## Verify

```powershell
py -3.12 -c "import torch; print(torch.cuda.is_available()); print(torch.version.cuda)"
```

Should print `True` and `12.8`.

## Running

```powershell
py -3.12 preprocess.py <video_id>
```
