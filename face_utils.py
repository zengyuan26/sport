"""人脸识别工具 — 可选依赖，未安装时退回手动标记"""
import os
import pickle
import logging

log = logging.getLogger(__name__)

HAS_FACE_RECOGNITION = False
try:
    import face_recognition
    import numpy as np
    HAS_FACE_RECOGNITION = True
except ImportError:
    log.warning("face_recognition 未安装，照片将进入手动标记队列")


def encode_face_from_image(image_path):
    """从图片提取第一张人脸编码，失败返回 None"""
    if not HAS_FACE_RECOGNITION:
        return None
    try:
        img = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(img)
        if encodings:
            return encodings[0]
    except Exception as e:
        log.warning(f"人脸提取失败 {image_path}: {e}")
    return None


def match_student(image_path, students_with_encodings):
    """将图片中的人脸与已知学员比对，返回 (student_id, confidence) 或 (None, None)"""
    if not HAS_FACE_RECOGNITION:
        return None, None
    unknown_enc = encode_face_from_image(image_path)
    if unknown_enc is None:
        return None, None

    THRESHOLD = 0.4       # 欧氏距离阈值，越小越严格（对中国儿童人脸收紧到 0.4）
    MIN_CONFIDENCE = 0.35  # 最低置信度，低于此值不自动归类

    best_id, best_dist = None, THRESHOLD
    second_dist = THRESHOLD
    for sid, known_blob in students_with_encodings:
        if not known_blob:
            continue
        try:
            known_enc = pickle.loads(known_blob)
            dist = np.linalg.norm(known_enc - unknown_enc)
            if dist < best_dist:
                second_dist = best_dist
                best_dist = dist
                best_id = sid
            elif dist < second_dist:
                second_dist = dist
        except Exception:
            continue

    if not best_id:
        return None, None

    confidence = max(0, 1 - best_dist / THRESHOLD)
    # 如果第一名和第二名差距太小（< 0.08），说明多人相似，不确定，拒绝自动归类
    margin = second_dist - best_dist
    if margin < 0.08 or confidence < MIN_CONFIDENCE:
        return None, None

    return best_id, round(confidence, 2)
