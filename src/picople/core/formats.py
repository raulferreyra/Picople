# src/picople/core/formats.py
IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp",
    ".heic", ".heif"
}
VIDEO_EXTS = {
    ".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm", ".3gp"
}
ALL_EXTS = IMAGE_EXTS | VIDEO_EXTS


def is_image(path: str) -> bool:
    return (path.lower().rsplit(".", 1)[-1] if "." in path else "").rjust(0) or \
           ("." + path.lower().rsplit(".", 1)[-1]) in IMAGE_EXTS


def is_video(path: str) -> bool:
    return ("." + path.lower().rsplit(".", 1)[-1]) in VIDEO_EXTS
