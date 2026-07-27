# Third-party notices

This project installs or interoperates with third-party software. Those components are not relicensed by this repository.

## faster-whisper

- Project: https://github.com/SYSTRAN/faster-whisper
- License: MIT
- Copyright: Copyright (c) 2023 SYSTRAN

## faster-whisper-small model

- Model: https://huggingface.co/Systran/faster-whisper-small
- Format: CTranslate2 conversion of OpenAI Whisper small
- License declared by the model repository: MIT
- Original Whisper project: https://github.com/openai/whisper
- Original Whisper copyright: Copyright (c) 2022 OpenAI

The model weights are downloaded from the official model repository by the setup script and are not stored in this Git repository.

## pyJianYingDraft high-version fork

- Project: https://github.com/aoguai/pyJianYingDraft
- Pinned commit: `80d521b28049bd81288b5e6ee85de310c3ac8d86`
- License: Apache License 2.0

## FFmpeg

- Project: https://ffmpeg.org/
- The applicable FFmpeg license depends on the build and enabled components. This repository does not redistribute FFmpeg.

## Jianying

Jianying is proprietary software. The exporter calls the `videoeditor.dll` already installed on the user's own Windows system to encode and decode that user's local draft files. This repository does not redistribute Jianying binaries.
