"""Kịch bản thu dữ liệu có nhãn. Nhãn = lời nhắc (người tự đóng vai làm theo).

Mỗi đoạn: (thời lượng s, nhãn mắt, nhãn hướng nhìn, lời nhắc không dấu trên màn hình, mong đợi, lời đọc)
  nhãn mắt: open | closed | any (không chấm theo frame)
  nhãn hướng nhìn: road | away
  mong đợi: OK | DROWSY | DISTRACTED | ANY

v2: lời nhắc được ĐỌC TO (giọng tiếng Việt của macOS). Ở v1 người đóng vai phải đọc lời nhắc trên màn hình nên
(1) nhắm mắt trễ ~2 s vì còn đọc, (2) quay đầu nhưng mắt vẫn liếc về màn hình -> nhãn "away" sai với thực tế.
Khi nhìn đi chỗ khác phải nhìn vào một VẬT THẬT (cửa sổ, bạn bên cạnh, điện thoại), không nhìn màn hình.
"""

PROTOCOLS = {
    # ~95 s: chấm độ chính xác chính
    "main": [
        (6, "open", "road", "Nhin thang, mo mat binh thuong (hieu chuan)", "ANY",
         "Nhìn thẳng vào màn hình, mở mắt bình thường"),
        (10, "any", "road", "Nhin thang, CHOP MAT tu nhien", "OK", "Chớp mắt tự nhiên"),
        (4, "closed", "road", "NHAM MAT 4 giay", "DROWSY", "Nhắm mắt"),
        (6, "open", "road", "Mo mat, nhin thang", "OK", "Mở mắt"),
        (3, "closed", "road", "NHAM MAT 3 giay", "DROWSY", "Nhắm mắt"),
        (6, "open", "road", "Mo mat, nhin thang", "OK", "Mở mắt"),
        (5, "open", "away", "NHIN RA BEN TRAI (vat that, khong nhin man hinh)", "DISTRACTED", "Nhìn sang trái"),
        (5, "open", "road", "Nhin thang", "OK", "Nhìn lại màn hình"),
        (5, "open", "away", "NHIN RA BEN PHAI (vat that, khong nhin man hinh)", "DISTRACTED", "Nhìn sang phải"),
        (5, "open", "road", "Nhin thang", "OK", "Nhìn lại màn hình"),
        (5, "open", "away", "CUI XUONG nhin dien thoai tren dui", "DISTRACTED", "Cúi xem điện thoại"),
        (5, "open", "road", "Nhin thang", "OK", "Nhìn lại màn hình"),
        (4, "any", "road", "NGAP 1 cai that to", "ANY", "Ngáp"),
        (5, "open", "road", "Nhin thang", "OK", "Nhìn thẳng"),
        (0.8, "closed", "road", "Nham mat NHANH roi mo (0.8s)", "OK", "Nhắm nhanh"),
        (6, "open", "road", "Mo mat, nhin thang", "OK", "Mở mắt"),
        (4, "closed", "road", "NHAM MAT 4 giay", "DROWSY", "Nhắm mắt"),
        (5, "open", "road", "Mo mat - ket thuc", "OK", "Mở mắt"),
    ],
    # Ca lỗi có chủ đích
    "failure": [
        (6, "open", "road", "Nhin thang, mo mat (hieu chuan)", "ANY", "Nhìn thẳng, mở mắt bình thường"),
        (5, "open", "road", "Mo mat, liec mat XUONG dong ho (dau giu yen)", "OK", "Liếc mắt xuống, giữ yên đầu"),
        (5, "open", "road", "Nhin thang", "OK", "Nhìn thẳng"),
        (5, "open", "road", "Lay TAY CHE 1 MAT, mat kia mo", "ANY", "Lấy tay che một mắt"),
        (5, "open", "road", "Nhin thang", "OK", "Bỏ tay ra, nhìn thẳng"),
        (5, "open", "away", "QUAY HAN SANG BEN (>60 do, nhin ra sau vai)", "DISTRACTED", "Quay hẳn ra sau vai"),
        (5, "open", "road", "Nhin thang", "OK", "Nhìn thẳng"),
        (5, "open", "away", "LIEC MAT sang trai, DAU GIU YEN", "DISTRACTED", "Chỉ liếc mắt sang trái, đầu giữ yên"),
        (5, "open", "road", "Nhin thang", "OK", "Nhìn thẳng"),
        (5, "open", "road", "LAY TAY CHE CAMERA", "ANY", "Lấy tay che camera"),
        (5, "open", "road", "Bo tay ra, nhin thang", "OK", "Bỏ tay ra, nhìn thẳng"),
    ],
}


def segments(name):
    t, out = 0.0, []
    for dur, eye, att, prompt, expect, speech in PROTOCOLS[name]:
        out.append({"start": round(t, 3), "end": round(t + dur, 3), "eye": eye, "attention": att,
                    "prompt": prompt, "expect": expect, "speech": speech})
        t += dur
    return out
