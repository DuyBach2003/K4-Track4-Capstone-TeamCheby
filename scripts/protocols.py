"""Kịch bản thu dữ liệu có nhãn. Nhãn = lời nhắc hiện trên màn hình (người tự đóng vai làm theo).

Mỗi đoạn: (thời lượng s, nhãn mắt, nhãn hướng nhìn, lời nhắc không dấu, mong đợi hệ thống)
  nhãn mắt: open | closed | any (không chấm theo frame)
  nhãn hướng nhìn: road | away
  mong đợi: OK | DROWSY | DISTRACTED | ANY
"""

PROTOCOLS = {
    # ~95 s: chấm độ chính xác chính
    "main": [
        (6, "open", "road", "Nhin thang, mo mat binh thuong (hieu chuan)", "ANY"),
        (10, "any", "road", "Nhin thang, CHOP MAT tu nhien", "OK"),
        (4, "closed", "road", "NHAM MAT 4 giay", "DROWSY"),
        (6, "open", "road", "Mo mat, nhin thang", "OK"),
        (3, "closed", "road", "NHAM MAT 3 giay", "DROWSY"),
        (6, "open", "road", "Mo mat, nhin thang", "OK"),
        (5, "open", "away", "QUAY DAU SANG TRAI (nhin cua so)", "DISTRACTED"),
        (5, "open", "road", "Nhin thang", "OK"),
        (5, "open", "away", "QUAY DAU SANG PHAI", "DISTRACTED"),
        (5, "open", "road", "Nhin thang", "OK"),
        (5, "open", "away", "CUI XUONG nhin dien thoai", "DISTRACTED"),
        (5, "open", "road", "Nhin thang", "OK"),
        (4, "any", "road", "NGAP 1 cai that to", "ANY"),
        (5, "open", "road", "Nhin thang", "OK"),
        (0.8, "closed", "road", "Nham mat NHANH roi mo (0.8s)", "OK"),
        (6, "open", "road", "Mo mat, nhin thang", "OK"),
        (4, "closed", "road", "NHAM MAT 4 giay", "DROWSY"),
        (5, "open", "road", "Mo mat - ket thuc", "OK"),
    ],
    # Ca lỗi có chủ đích: đeo kính râm / kính cận phản sáng, cúi mà mắt vẫn mở, che mặt, tắt đèn
    "failure": [
        (6, "open", "road", "Nhin thang, mo mat (hieu chuan)", "ANY"),
        (5, "open", "road", "DEO KINH RAM, mo mat nhin thang", "OK"),
        (4, "closed", "road", "(van deo kinh) NHAM MAT 4 giay", "DROWSY"),
        (6, "open", "road", "THAO KINH, nhin thang", "OK"),
        (5, "open", "road", "Mo mat, nhin XUONG 15 do (nhu nhin dong ho xe)", "OK"),
        (5, "open", "road", "Nhin thang", "OK"),
        (5, "open", "road", "Lay TAY CHE 1 NUA MAT", "ANY"),
        (5, "open", "road", "Nhin thang", "OK"),
        (5, "open", "away", "QUAY HAN SANG BEN (>60 do)", "DISTRACTED"),
        (5, "open", "road", "Nhin thang", "OK"),
        (6, "open", "road", "TAT DEN / quay lung ve cua so (nguoc sang)", "ANY"),
        (5, "open", "road", "Bat den lai, nhin thang", "OK"),
    ],
}


def segments(name):
    t, out = 0.0, []
    for dur, eye, att, prompt, expect in PROTOCOLS[name]:
        out.append({"start": round(t, 3), "end": round(t + dur, 3), "eye": eye, "attention": att,
                    "prompt": prompt, "expect": expect})
        t += dur
    return out
