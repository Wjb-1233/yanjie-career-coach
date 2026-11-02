"""视频面试的镜头表现分析。

用 MediaPipe FaceLandmarker（478 关键点，含虹膜）逐帧算客观指标：
出镜率、眼神稳定率、头部稳定度、表情活跃度、构图与光线。
只输出可复现的度量，不做「性格」或「外貌」评价。
"""

from __future__ import annotations

import statistics
from pathlib import Path

import cv2

MODEL_PATH = Path(__file__).resolve().parents[3] / ".models" / "face_landmarker.task"
SAMPLE_FPS = 2.0
MAX_FRAMES = 180

# FaceMesh 关键点索引
LEFT_EYE_OUTER, LEFT_EYE_INNER = 33, 133
RIGHT_EYE_OUTER, RIGHT_EYE_INNER = 263, 362
LEFT_IRIS = (468, 469, 470, 471, 472)
RIGHT_IRIS = (473, 474, 475, 476, 477)
NOSE_TIP = 1
CHIN = 152
MOUTH_LEFT, MOUTH_RIGHT = 61, 291
LIP_TOP, LIP_BOTTOM = 13, 14


def _import_mediapipe():
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    return mp, mp_python, vision


_landmarker = None
# 复用同一个 landmarker 时，时间戳必须全局递增，否则 mediapipe 会报错
_ts_offset = 0


def _enabled() -> bool:
    return MODEL_PATH.exists()


def _get_landmarker():
    """缓存 FaceLandmarker 实例，避免每次分析都重新加载模型（约 17 秒）。"""
    global _landmarker
    if _landmarker is not None:
        return _landmarker
    _mp, mp_python, vision = _import_mediapipe()
    options = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
    )
    _landmarker = vision.FaceLandmarker.create_from_options(options)
    return _landmarker


def warmup() -> bool:
    """预热人脸模型；失败不影响主流程。"""
    if not _enabled():
        return False
    try:
        _get_landmarker()
        return True
    except Exception:  # noqa: BLE001
        return False


def _iris_ratio(landmarks, iris_ids, outer: int, inner: int, axis: str) -> float | None:
    points = [landmarks[index] for index in iris_ids]
    center = (
        sum(point.x for point in points) / len(points),
        sum(point.y for point in points) / len(points),
    )
    a, b = landmarks[outer], landmarks[inner]
    if axis == "x":
        span = b.x - a.x
        return (center[0] - a.x) / span if abs(span) > 1e-6 else None
    span = b.y - a.y
    return (center[1] - a.y) / span if abs(span) > 1e-6 else None


def _frame_metrics(landmarks) -> dict:
    xs = [point.x for point in landmarks]
    ys = [point.y for point in landmarks]
    left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
    width, height = max(1e-6, right - left), max(1e-6, bottom - top)

    eye_mid_x = (landmarks[LEFT_EYE_OUTER].x + landmarks[RIGHT_EYE_OUTER].x) / 2
    eye_mid_y = (landmarks[LEFT_EYE_OUTER].y + landmarks[RIGHT_EYE_OUTER].y) / 2
    yaw = (landmarks[NOSE_TIP].x - eye_mid_x) / width
    pitch = (landmarks[NOSE_TIP].y - eye_mid_y) / height

    left_ratio = _iris_ratio(landmarks, LEFT_IRIS, LEFT_EYE_OUTER, LEFT_EYE_INNER, "x")
    right_ratio = _iris_ratio(landmarks, RIGHT_IRIS, RIGHT_EYE_OUTER, RIGHT_EYE_INNER, "x")
    eye_centered = (
        left_ratio is not None
        and right_ratio is not None
        and 0.25 <= left_ratio <= 0.75
        and 0.25 <= right_ratio <= 0.75
    )

    mouth_width = abs(landmarks[MOUTH_LEFT].x - landmarks[MOUTH_RIGHT].x) / width
    mouth_open = abs(landmarks[LIP_BOTTOM].y - landmarks[LIP_TOP].y) / height

    return {
        "yaw": yaw,
        "pitch": pitch,
        "eyeCentered": eye_centered,
        "mouth": mouth_width,
        "mouthOpen": mouth_open,
        "centerX": (left + right) / 2,
        "centerY": (top + bottom) / 2,
        "faceWidth": width,
    }


def analyze_video(path: Path) -> dict:
    """逐帧采样分析，返回镜头指标与一句整体判断。"""
    global _ts_offset
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return {"available": False, "reason": "视频无法打开或格式不支持", "tips": []}
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = total / fps if fps else 0

    step = max(1, int(round(fps / SAMPLE_FPS)))
    if not _enabled():
        capture.release()
        return {
            "available": False,
            "reason": "未安装人脸模型（.models/face_landmarker.task）",
            "durationSeconds": round(duration, 1),
            "resolution": [width, height],
        }

    mp, mp_python, vision = _import_mediapipe()

    frames = 0
    faces = 0
    centered = 0
    yaws: list[float] = []
    pitches: list[float] = []
    mouths: list[float] = []
    centers_x: list[float] = []
    centers_y: list[float] = []
    brightness: list[float] = []

    landmarker = _get_landmarker()
    if True:
        index = 0
        while frames < MAX_FRAMES:
            ok, frame = capture.read()
            if not ok:
                break
            if index % step == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                brightness.append(float(rgb.mean()))
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = _ts_offset + (int(index / fps * 1000) if fps else index * 40)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)
                frames += 1
                if result.face_landmarks:
                    faces += 1
                    metrics = _frame_metrics(result.face_landmarks[0])
                    yaws.append(metrics["yaw"])
                    pitches.append(metrics["pitch"])
                    mouths.append(metrics["mouth"])
                    centers_x.append(metrics["centerX"])
                    centers_y.append(metrics["centerY"])
                    if metrics["eyeCentered"] and abs(metrics["yaw"]) < 0.12 and abs(metrics["pitch"]) < 0.22:
                        centered += 1
            index += 1
    capture.release()
    _ts_offset += int(duration * 1000) + 1000

    if frames == 0:
        return {"available": False, "reason": "视频无法解码"}

    face_ratio = round(faces / frames, 3)
    eye_contact = round(centered / faces, 3) if faces else 0.0
    yaw_std = round(statistics.pstdev(yaws), 3) if len(yaws) > 1 else 0.0
    pitch_std = round(statistics.pstdev(pitches), 3) if len(pitches) > 1 else 0.0
    head_stability = round(max(0.0, 1 - min(1.0, (yaw_std + pitch_std) * 5)), 3)
    mouth_variation = round(statistics.pstdev(mouths), 4) if len(mouths) > 1 else 0.0
    offset = (
        round(((statistics.fmean(centers_x) - 0.5) ** 2 + (statistics.fmean(centers_y) - 0.5) ** 2) ** 0.5, 3)
        if centers_x else 0.5
    )
    mean_brightness = round(statistics.fmean(brightness), 1) if brightness else 0.0

    tips: list[str] = []
    if face_ratio < 0.85:
        tips.append(f"出镜率 {round(face_ratio * 100)}%，有相当时间没对准镜头")
    if eye_contact < 0.6:
        tips.append(f"眼神在镜头上的时间只有 {round(eye_contact * 100)}%，看屏幕会让对方觉得没交流")
    if head_stability < 0.6:
        tips.append("头部晃动偏多，回答时尽量让脸保持在画面中间")
    if offset > 0.12:
        tips.append("面部偏离画面中心，建议把摄像头调到与眼睛平齐")
    if mean_brightness < 70:
        tips.append("画面偏暗，补光或面向窗户会更清楚")
    if mouth_variation < 0.004 and faces > 5:
        tips.append("表情几乎没变化，适当放松面部会更自然")

    return {
        "available": True,
        "durationSeconds": round(duration, 1),
        "resolution": [width, height],
        "sampledFrames": frames,
        "faceRatio": face_ratio,
        "eyeContactRatio": eye_contact,
        "headStability": head_stability,
        "yawStd": yaw_std,
        "pitchStd": pitch_std,
        "mouthVariation": mouth_variation,
        "centerOffset": offset,
        "brightness": mean_brightness,
        "tips": tips,
    }
