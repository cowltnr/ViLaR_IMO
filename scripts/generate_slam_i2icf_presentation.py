#!/usr/bin/python3
"""Generate the editable SLAM/I2ICF research-direction presentation.

Run with Ubuntu's system Python because python3-uno is installed there:
    /usr/bin/python3 scripts/generate_slam_i2icf_presentation.py
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import time

import uno
from com.sun.star.awt import Point, Size
from com.sun.star.beans import PropertyValue


class ParagraphAdjust:
    """UNO enum values without relying on optional enum import proxies."""

    LEFT = uno.Enum("com.sun.star.style.ParagraphAdjust", "LEFT")
    CENTER = uno.Enum("com.sun.star.style.ParagraphAdjust", "CENTER")
    RIGHT = uno.Enum("com.sun.star.style.ParagraphAdjust", "RIGHT")


class TextVerticalAdjust:
    """UNO enum values without relying on optional enum import proxies."""

    TOP = uno.Enum("com.sun.star.drawing.TextVerticalAdjust", "TOP")
    CENTER = uno.Enum("com.sun.star.drawing.TextVerticalAdjust", "CENTER")


ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT_STEM = ROOT / "SDV_Robocar_SLAM_I2ICF_직관적_7장"
SOFFICE_PIPE = "sdv_robocar_presentation"
SOFFICE_PROFILE = pathlib.Path("/tmp/sdv_robocar_presentation_profile")

PAGE_W = 33867
PAGE_H = 19050
MARGIN_X = 1250
TITLE_Y = 750
CONTENT_TOP = 2700

NAVY = 0x10243E
BLUE = 0x2563EB
CYAN = 0x0891B2
TEAL = 0x0F766E
GREEN = 0x15803D
ORANGE = 0xEA580C
RED = 0xDC2626
PURPLE = 0x7C3AED
SLATE = 0x475569
MID = 0x94A3B8
LIGHT = 0xE2E8F0
PALE_BLUE = 0xEFF6FF
PALE_CYAN = 0xECFEFF
PALE_GREEN = 0xF0FDF4
PALE_ORANGE = 0xFFF7ED
PALE_PURPLE = 0xF5F3FF
PALE_RED = 0xFEF2F2
WHITE = 0xFFFFFF
BLACK = 0x0F172A

FONT = "Noto Sans CJK KR"


def prop(name: str, value):
    item = PropertyValue()
    item.Name = name
    item.Value = value
    return item


def connect_office():
    SOFFICE_PROFILE.mkdir(parents=True, exist_ok=True)
    command = [
        "/usr/bin/libreoffice",
        "--headless",
        f"-env:UserInstallation={SOFFICE_PROFILE.as_uri()}",
        f"--accept=pipe,name={SOFFICE_PIPE};urp;StarOffice.ComponentContext",
        "--norestore",
        "--nodefault",
        "--nofirststartwizard",
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    local_ctx = uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_ctx
    )
    last_error = None
    for _ in range(50):
        try:
            ctx = resolver.resolve(
                f"uno:pipe,name={SOFFICE_PIPE};urp;StarOffice.ComponentContext"
            )
            desktop = ctx.ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.Desktop", ctx
            )
            return process, desktop
        except Exception as exc:  # LibreOffice may need a short startup interval.
            last_error = exc
            time.sleep(0.1)
    process.terminate()
    raise RuntimeError(f"Unable to connect to LibreOffice: {last_error}")


def rgb(color: int) -> int:
    return int(color)


def shape(doc, page, service: str, x: int, y: int, w: int, h: int):
    item = doc.createInstance(service)
    item.Position = Point(x, y)
    item.Size = Size(w, h)
    page.add(item)
    return item


def set_text(
    item,
    text: str,
    size: float = 16,
    color: int = BLACK,
    bold: bool = False,
    align=ParagraphAdjust.LEFT,
    valign=TextVerticalAdjust.CENTER,
    font: str = FONT,
):
    item.String = text
    item.CharFontName = font
    item.CharHeight = float(size)
    item.CharColor = rgb(color)
    item.CharWeight = 150.0 if bold else 100.0
    item.ParaAdjust = align
    item.TextVerticalAdjust = valign
    item.TextLeftDistance = 260
    item.TextRightDistance = 260
    item.TextUpperDistance = 150
    item.TextLowerDistance = 150
    return item


def text_box(doc, page, x, y, w, h, text, **kwargs):
    item = shape(doc, page, "com.sun.star.drawing.TextShape", x, y, w, h)
    item.FillStyle = 0
    item.LineStyle = 0
    return set_text(item, text, **kwargs)


def box(
    doc,
    page,
    x,
    y,
    w,
    h,
    text,
    fill=WHITE,
    line=LIGHT,
    radius=180,
    **kwargs,
):
    item = shape(doc, page, "com.sun.star.drawing.RectangleShape", x, y, w, h)
    item.FillColor = rgb(fill)
    item.LineColor = rgb(line)
    item.LineWidth = 35
    item.CornerRadius = radius
    return set_text(item, text, **kwargs)


def line(doc, page, x1, y1, x2, y2, color=SLATE, width=55):
    item = shape(
        doc,
        page,
        "com.sun.star.drawing.LineShape",
        x1,
        y1,
        max(1, x2 - x1),
        max(1, y2 - y1),
    )
    item.LineColor = rgb(color)
    item.LineWidth = width
    return item


def circle(doc, page, x, y, d, fill, line_color=WHITE):
    item = shape(doc, page, "com.sun.star.drawing.EllipseShape", x, y, d, d)
    item.FillColor = rgb(fill)
    item.LineColor = rgb(line_color)
    item.LineWidth = 35
    return item


def pill(doc, page, x, y, w, text, fill, color=WHITE):
    return box(
        doc,
        page,
        x,
        y,
        w,
        620,
        text,
        fill=fill,
        line=fill,
        radius=300,
        size=11,
        color=color,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )


def slide_title(doc, page, number: int, title: str, section: str):
    pill(doc, page, MARGIN_X, TITLE_Y, 1800, section, BLUE if section == "SLAM" else TEAL)
    text_box(
        doc,
        page,
        MARGIN_X + 2100,
        TITLE_Y - 80,
        28200,
        1000,
        title,
        size=25,
        color=NAVY,
        bold=True,
    )
    text_box(
        doc,
        page,
        31700,
        17800,
        800,
        450,
        str(number),
        size=10,
        color=MID,
        align=ParagraphAdjust.RIGHT,
    )
    line(doc, page, MARGIN_X, 2050, 32600, 2050, LIGHT, 25)


def add_notes(doc, page, note_text: str):
    notes = page.getNotesPage()
    note = shape(doc, notes, "com.sun.star.drawing.TextShape", 1200, 1200, 30000, 7000)
    note.FillStyle = 0
    note.LineStyle = 0
    set_text(note, note_text, size=14, color=BLACK, valign=TextVerticalAdjust.TOP)


def source_footer(doc, page, text: str):
    text_box(
        doc,
        page,
        MARGIN_X,
        17710,
        29000,
        420,
        text,
        size=7.5,
        color=MID,
    )


def new_slide(doc, pages):
    if pages.getCount() == 1 and getattr(pages.getByIndex(0), "Name", "") == "":
        page = pages.getByIndex(0)
    else:
        page = pages.insertNewByIndex(pages.getCount())
    page.Width = PAGE_W
    page.Height = PAGE_H
    return page


def add_title_slide(doc, page):
    bg = shape(doc, page, "com.sun.star.drawing.RectangleShape", 0, 0, PAGE_W, PAGE_H)
    bg.FillColor = rgb(NAVY)
    bg.LineStyle = 0
    circle(doc, page, 27000, -1300, 9000, BLUE, BLUE)
    circle(doc, page, 29200, 11200, 6200, TEAL, TEAL)
    pill(doc, page, 1700, 1600, 2750, "연구실 내부 회의", CYAN)
    text_box(
        doc,
        page,
        1700,
        3500,
        27000,
        3100,
        "SDV Robocar\n연구 고도화 방향",
        size=34,
        color=WHITE,
        bold=True,
        valign=TextVerticalAdjust.TOP,
    )
    text_box(
        doc,
        page,
        1800,
        7550,
        26500,
        1800,
        "SLAM 기반 실시간 경로 생성\nI2ICF 기반 이기종 이동체 정보 공유",
        size=20,
        color=0xDCEBFF,
        bold=False,
        valign=TextVerticalAdjust.TOP,
    )
    box(
        doc,
        page,
        1700,
        11300,
        27000,
        2550,
        "사전 정의 경로 선택에서\n실시간 경로 생성 · 의미 기반 선택 · 협력 정보 공유로",
        fill=0x183858,
        line=0x2B4B68,
        size=21,
        color=WHITE,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    text_box(
        doc,
        page,
        1750,
        16500,
        27000,
        500,
        "발표 10분  |  SLAM 중심  ·  I2ICF 1장  ·  Next Step 1장",
        size=11,
        color=0xAFC5DE,
    )
    add_notes(
        doc,
        page,
        "발표 목표: 현재 시스템의 검증된 기준선을 유지하면서, SLAM 기반 동적 경로 생성과 I2ICF 기반 이기종 정보 공유를 어떤 순서로 연구할지 합의한다.",
    )


def add_agenda_slide(doc, page):
    slide_title(doc, page, 2, "오늘 회의에서 확인할 것", "목차")
    text_box(
        doc,
        page,
        1500,
        2500,
        30000,
        700,
        "문제 → 동작 방식 → 다음 주 실행 순서로 설명",
        size=13,
        color=SLATE,
    )
    box(
        doc,
        page,
        1200,
        3500,
        9800,
        9800,
        "01\n\n왜 바꾸는가?\n\n• 기존 Route의 한계\n• 실시간 Path 생성\n• 장애물 자동 우회",
        fill=PALE_BLUE,
        line=BLUE,
        size=18,
        color=NAVY,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    pill(doc, page, 2850, 3900, 6500, "SLAM  ·  3장", BLUE)
    box(
        doc,
        page,
        12050,
        3500,
        9800,
        9800,
        "02\n\n어떻게 공유하는가?\n\n• LIMO A가 발견\n• 서버가 정보 정리\n• Robot B가 자체 판단",
        fill=PALE_CYAN,
        line=TEAL,
        size=18,
        color=NAVY,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    pill(doc, page, 13700, 3900, 6500, "I2ICF  ·  1장", TEAL)
    box(
        doc,
        page,
        22900,
        3500,
        9800,
        9800,
        "03\n\n다음 주에 무엇을 하는가?\n\n• Isaac Sim Map 생성\n• Localization 확인\n• 단일 Path·우회 확인",
        fill=PALE_ORANGE,
        line=ORANGE,
        size=18,
        color=NAVY,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    pill(doc, page, 24550, 3900, 6500, "NEXT STEP  ·  1장", ORANGE)
    box(
        doc,
        page,
        4300,
        14500,
        25000,
        1500,
        "현재 방식 이해  →  SLAM 기반 Path 생성  →  일주일 안에 검증",
        fill=NAVY,
        line=NAVY,
        size=17,
        color=WHITE,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    add_notes(
        doc,
        page,
        "SLAM 세 장을 중심으로 현재 문제와 Path 생성, 자동 우회를 설명한다. I2ICF는 환경정보 공유 사례 한 장으로 줄이고 마지막에는 다음 주 실행 계획을 제시한다.",
    )


def add_current_slide(doc, page):
    slide_title(doc, page, 3, "왜 Predefined Route 선택 방식을 바꿔야 하는가?", "SLAM")
    box(
        doc,
        page,
        1300,
        2900,
        14000,
        10100,
        "\n\n① routes.py에 wp1~wp5 좌표를 수동 정의\n\n② Goal이 포함된 Route만 Candidate로 제한\n\n③ VLM은 Candidate 이름 중 하나만 선택\n\n④ Point Follower / Pure Pursuit가 추종",
        fill=PALE_BLUE,
        line=0xBFDBFE,
        size=18,
        color=NAVY,
        bold=False,
        valign=TextVerticalAdjust.TOP,
    )
    pill(doc, page, 2200, 3300, 2500, "현재", BLUE)
    box(
        doc,
        page,
        16900,
        2900,
        15600,
        10100,
        "\n\n• 새로운 장애물 배치에 맞는 Path 형상 생성 불가\n\n• Route 추가·수정에 수작업 필요\n\n• Map 변화와 현재 Pose가 선택 과정에 직접 반영되지 않음\n\n• VLM이 의미를 판단해도 선택 공간은 wp1~wp5로 고정",
        fill=PALE_RED,
        line=0xFECACA,
        size=18,
        color=NAVY,
        valign=TextVerticalAdjust.TOP,
    )
    pill(doc, page, 17800, 3300, 2500, "한계", RED)
    box(
        doc,
        page,
        3900,
        14200,
        26000,
        1800,
        "Predefined Route 선택  →  SLAM Map 기반 Dynamic Path 생성",
        fill=NAVY,
        line=NAVY,
        size=21,
        color=WHITE,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    source_footer(doc, page, "근거: README.md §4–6, ARCHITECTURE.md의 현재 구조 검증 내용")
    add_notes(
        doc,
        page,
        "현재 VLM은 경로를 생성하지 않는다. wp1~wp5 중 하나를 선택할 뿐이다. 연구 목표는 기준선을 삭제하는 것이 아니라 비교 대상으로 보존하고, 동적 생성 방식을 별도 후보 방식으로 추가하는 것이다.",
    )


def add_slam_architecture_slide(doc, page):
    slide_title(doc, page, 4, "제안 구조 — SLAM은 Map, Planner는 Path", "SLAM")
    text_box(
        doc,
        page,
        1500,
        2550,
        30000,
        650,
        "역할을 분리해야 안전성과 실험 해석이 명확해진다",
        size=13,
        color=SLATE,
    )
    stages = [
        ("1", "Sensors", "Camera · 2D LiDAR\nOdometry", PALE_BLUE, BLUE),
        ("2", "SLAM Toolbox", "지도 + 현재 위치·자세\n/map, map→odom", PALE_CYAN, CYAN),
        ("3", "Global Costmap", "고정 Map + 장애물\nFootprint + Semantic Cost", PALE_GREEN, GREEN),
        ("4", "Candidate Generator", "K-Shortest Paths\n+ Hybrid-A* 보정", PALE_ORANGE, ORANGE),
    ]
    x = 1200
    for idx, title, detail, fill, accent in stages:
        box(
            doc,
            page,
            x,
            3700,
            6900,
            3400,
            f"{title}\n{detail}",
            fill=fill,
            line=accent,
            size=15,
            color=NAVY,
            bold=True,
            align=ParagraphAdjust.CENTER,
        )
        circle(doc, page, x + 250, 3900, 600, accent, accent)
        text_box(
            doc,
            page,
            x + 250,
            3900,
            600,
            600,
            idx,
            size=11,
            color=WHITE,
            bold=True,
            align=ParagraphAdjust.CENTER,
        )
        x += 8200
    text_box(doc, page, 7800, 4700, 700, 900, "→", size=25, color=MID, bold=True, align=ParagraphAdjust.CENTER)
    text_box(doc, page, 16000, 4700, 700, 900, "→", size=25, color=MID, bold=True, align=ParagraphAdjust.CENTER)
    text_box(doc, page, 24200, 4700, 700, 900, "→", size=25, color=MID, bold=True, align=ParagraphAdjust.CENTER)

    lower = [
        ("Hard Filter\n충돌 · 폭 · 곡률 · 회전 반경", PALE_RED, RED),
        ("VLM Selector\n사람 · 바닥 · 사용자 요청", PALE_PURPLE, PURPLE),
        ("Safety Validator + Controller\n검증 성공 시에만 주행", PALE_GREEN, GREEN),
    ]
    x_positions = [2700, 12100, 21500]
    for xpos, (text, fill, accent) in zip(x_positions, lower):
        box(
            doc,
            page,
            xpos,
            8900,
            7800,
            3000,
            text,
            fill=fill,
            line=accent,
            size=16,
            color=NAVY,
            bold=True,
            align=ParagraphAdjust.CENTER,
        )
    text_box(doc, page, 10550, 9850, 1200, 800, "→", size=25, color=MID, bold=True, align=ParagraphAdjust.CENTER)
    text_box(doc, page, 19950, 9850, 1200, 800, "→", size=25, color=MID, bold=True, align=ParagraphAdjust.CENTER)
    box(
        doc,
        page,
        4300,
        13200,
        25000,
        2200,
        "후보 A: 최단 경로   |   후보 B: 장애물 왼쪽 우회   |   후보 C: 장애물 오른쪽 우회",
        fill=NAVY,
        line=NAVY,
        size=18,
        color=WHITE,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    source_footer(doc, page, "참고 기술: ROS2 Humble slam_toolbox, Nav2 Costmap2D, Smac Hybrid-A* 경로 계획기")
    add_notes(
        doc,
        page,
        "SLAM이 길을 생성한다고 표현하면 안 된다. SLAM은 /map과 위치·자세를 제공한다. 전역 비용지도가 실시간 장애물과 차체 외곽을 합치고, 경로 계획기가 후보를 생성한다. 안전 필터를 통과한 후보만 VLM에 전달한다.",
    )


def add_detour_slide(doc, page):
    slide_title(doc, page, 5, "장애물 발견 시 자동 우회는 어떻게 동작하는가?", "SLAM")
    # Schematic map area
    map_box = box(doc, page, 1300, 2900, 19000, 9400, "", fill=0xF8FAFC, line=LIGHT)
    box(doc, page, 3700, 5100, 14100, 3800, "", fill=WHITE, line=0xCBD5E1, radius=50)
    circle(doc, page, 2400, 6600, 1050, BLUE, BLUE)
    text_box(doc, page, 2050, 7750, 1800, 500, "출발", size=10, color=BLUE, bold=True, align=ParagraphAdjust.CENTER)
    circle(doc, page, 18200, 6600, 1050, GREEN, GREEN)
    text_box(doc, page, 17850, 7750, 1800, 500, "목표", size=10, color=GREEN, bold=True, align=ParagraphAdjust.CENTER)
    box(doc, page, 9900, 6000, 2100, 2100, "사람\n/ 장애물", fill=PALE_RED, line=RED, size=13, color=RED, bold=True, align=ParagraphAdjust.CENTER)

    # Candidate routes represented by thick line segments.
    for (x1, y1, x2, y2) in [(3450, 7100, 9600, 7100), (12300, 7100, 18200, 7100)]:
        line(doc, page, x1, y1, x2, y2, RED, 110)
    for points in [
        [(3450, 6800, 6800, 4100), (6800, 4100, 14600, 4100), (14600, 4100, 18200, 6800)],
        [(3450, 7400, 6800, 10100), (6800, 10100, 14600, 10100), (14600, 10100, 18200, 7400)],
    ]:
        color = BLUE if points[0][1] == 6800 else ORANGE
        for x1, y1, x2, y2 in points:
            line(doc, page, x1, y1, x2, y2, color, 100)
    text_box(doc, page, 6200, 3300, 5100, 500, "후보 B: 위쪽 우회", size=11, color=BLUE, bold=True)
    text_box(doc, page, 6200, 10600, 5100, 500, "후보 C: 아래쪽 우회", size=11, color=ORANGE, bold=True)
    text_box(doc, page, 6200, 8000, 4100, 500, "기존 경로 무효화", size=11, color=RED, bold=True)

    steps = [
        ("1", "감지", "카메라–LiDAR가\n새 장애물 탐지"),
        ("2", "정지", "Local Safety가\n우선 Stop"),
        ("3", "갱신", "Obstacle Layer를\nCostmap에 반영"),
        ("4", "재계획", "현재 경로 무효화\nK개 후보 재생성"),
        ("5", "재개", "검증 + VLM 선택\n통과 시에만 이동"),
    ]
    y = 3100
    for num, title, desc in steps:
        circle(doc, page, 22000, y + 250, 700, TEAL, TEAL)
        text_box(doc, page, 22000, y + 250, 700, 700, num, size=11, color=WHITE, bold=True, align=ParagraphAdjust.CENTER)
        box(doc, page, 23000, y, 9300, 1450, f"{title}  |  {desc}", fill=PALE_CYAN, line=0xA5F3FC, size=13, color=NAVY, bold=True)
        y += 1900
    box(
        doc,
        page,
        2600,
        13900,
        28700,
        1800,
        "임시 장애물은 SLAM Map에 영구 고정하지 않고 Obstacle Layer에서 관리",
        fill=PALE_ORANGE,
        line=0xFDBA74,
        size=17,
        color=ORANGE,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    source_footer(doc, page, "안전 원칙: VLM 출력 무효·시간 초과 → 정지 유지, /sim/cmd_vel 발행자는 하나만 활성화")
    add_notes(
        doc,
        page,
        "우회 시작 조건은 장애물 감지다. 먼저 정지하고, 임시 장애물을 비용지도의 장애물 계층에 넣어 현재 경로를 무효화한다. 새로운 후보를 생성한 후 검증된 경로만 선택한다. 통신이나 VLM이 실패하면 주행을 재개하지 않는다.",
    )


def add_i2icf_architecture_slide(doc, page):
    slide_title(doc, page, 6, "LIMO A가 본 장애물을 Robot B가 먼저 피하려면?", "I2ICF")
    text_box(
        doc,
        page,
        1500,
        2500,
        30000,
        700,
        "주행 명령이 아니라 환경정보를 공유하고, 각 이동체가 자기 Path를 다시 만든다",
        size=13,
        color=SLATE,
    )
    columns = [
        (
            1300,
            "① 발견  |  LIMO A",
            "Camera · LiDAR\n\n사람과 러그 감지\n↓\n무엇 · 어디 · 언제\n위치와 시간 함께 공유",
            PALE_BLUE,
            BLUE,
        ),
        (
            11950,
            "② 정리  |  Shared Server",
            "여러 이동체의 관측 수신\n\n같은 장애물은 하나로\n오래된 정보는 제거\n↓\n최신 환경정보 전달",
            PALE_PURPLE,
            PURPLE,
        ),
        (
            22600,
            "③ 각자 판단  |  Robot B",
            "내 차체로 통과 가능한가?\n↓\n내 Costmap 갱신\n내 우회 Path 생성\n↓\nLocal Sensor로 최종 확인",
            PALE_GREEN,
            GREEN,
        ),
    ]
    for xpos, heading, detail, fill, accent in columns:
        box(doc, page, xpos, 3500, 9200, 8500, detail, fill=fill, line=accent, size=17, color=NAVY, bold=True, align=ParagraphAdjust.CENTER)
        pill(doc, page, xpos + 950, 3900, 7300, heading, accent)
    text_box(doc, page, 10400, 6500, 1500, 800, "→", size=28, color=TEAL, bold=True, align=ParagraphAdjust.CENTER)
    text_box(doc, page, 21050, 6500, 1500, 800, "→", size=28, color=TEAL, bold=True, align=ParagraphAdjust.CENTER)
    text_box(doc, page, 9300, 7600, 3600, 1000, "환경정보\n공유", size=10, color=TEAL, bold=True, align=ParagraphAdjust.CENTER)
    text_box(doc, page, 19900, 7600, 3900, 1000, "최신 정보\n전달", size=10, color=TEAL, bold=True, align=ParagraphAdjust.CENTER)
    box(
        doc,
        page,
        2600,
        13200,
        28700,
        2200,
        "발견 → 공유 → 각자 판단\n같은 환경정보라도 차량 크기와 구동 방식에 따라 다른 Path를 선택",
        fill=NAVY,
        line=NAVY,
        size=18,
        color=WHITE,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    source_footer(doc, page, "연구 범위: 다중 이동체 환경정보 공유만 포함  |  intent 해석·policy control 제외")
    add_notes(
        doc,
        page,
        "LIMO A가 사람과 러그를 발견해 위치와 시간을 공유하면 서버는 중복과 오래된 정보를 정리한다. Robot B는 공유된 주행 명령을 따르는 것이 아니라 자신의 Costmap과 차량 특성으로 우회 Path를 다시 만들고, Local Sensor로 최종 안전을 확인한다.",
    )


def add_heterogeneous_slide(doc, page):
    slide_title(doc, page, 7, "이기종 실험 — 같은 정보, 다른 Path 판단", "I2ICF")
    # Scenario matrix
    headers = ["공유 상황", "LIMO\n애커먼 조향", "소형 로봇\n차동 구동", "무인기\n관측자"]
    col_x = [1300, 9000, 17000, 25000]
    col_w = [7200, 7300, 7300, 7300]
    for x, w, header in zip(col_x, col_w, headers):
        box(doc, page, x, 3000, w, 1200, header, fill=NAVY, line=NAVY, size=13, color=WHITE, bold=True, align=ParagraphAdjust.CENTER)
    rows = [
        ("좁은 통로", "차체 폭으로\n통과 불가", "통과 가능", "영향 없음"),
        ("두꺼운 러그", "미끄럼 위험\n높은 비용", "검증 결과에 따라\n다른 비용", "상공 관측"),
        ("낮은 장애물", "2D LiDAR\n사각 가능", "깊이 센서로\n재확인", "원거리 공유"),
        ("임시 사람", "유효시간 동안 우회", "유효시간 동안 우회", "위치 갱신"),
    ]
    y = 4350
    for ridx, row in enumerate(rows):
        fill = WHITE if ridx % 2 == 0 else 0xF8FAFC
        for x, w, cell in zip(col_x, col_w, row):
            box(doc, page, x, y, w, 1450, cell, fill=fill, line=LIGHT, radius=30, size=12.5, color=NAVY, bold=(x == col_x[0]), align=ParagraphAdjust.CENTER)
        y += 1450

    box(
        doc,
        page,
        1300,
        10600,
        15100,
        4400,
        "Shared Event Schema (공유 환경 사건 형식)\n\n출처 이동체(source_mo_id) · 지도(map_id) · 위치/불확실성(pose/covariance)\n분류(class) · 형상(geometry) · 신뢰도(confidence)\n시각(timestamp) · 유효시간(TTL) · 근거(evidence_uri) · 서명(signature)",
        fill=PALE_CYAN,
        line=TEAL,
        size=12.5,
        color=NAVY,
        bold=True,
        valign=TextVerticalAdjust.TOP,
    )
    box(
        doc,
        page,
        17100,
        10600,
        15400,
        4400,
        "비교 조건\n\nS0  정보 공유 없음\nS1  Raw JSON 공유\nS2  TTL · Confidence 기반 공유\nS3  Capability-aware Sharing",
        fill=PALE_PURPLE,
        line=PURPLE,
        size=14,
        color=NAVY,
        bold=True,
        valign=TextVerticalAdjust.TOP,
    )
    box(
        doc,
        page,
        3600,
        15600,
        26500,
        1050,
        "Metrics  |  도달률 · Replan 횟수 · 이동거리 · 공유 지연 · Stale Error · Capability Mismatch · 안전 유지",
        fill=PALE_ORANGE,
        line=ORANGE,
        size=13,
        color=ORANGE,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    source_footer(doc, page, "참고: Symbiotic Navigation, Cooperative Costmap with Lifelong Learning, Open-RMF")
    add_notes(
        doc,
        page,
        "핵심 실험은 동일한 사건이 이동체별로 다른 비용이 된다는 점이다. 첫 단계는 공통 지도를 사용해 정보 공유 효과만 분리한다. 이후 각 이동체의 독립 SLAM과 지도 정합으로 확장한다.",
    )


def add_roadmap_slide(doc, page):
    slide_title(doc, page, 7, "Next Step — 다음 주에 어디까지 만들 것인가?", "NEXT")
    box(
        doc,
        page,
        3300,
        2600,
        27200,
        1500,
        "목표  |  Isaac Sim에서 SLAM Map을 저장하고, 한 Goal까지 Path를 만든다",
        fill=NAVY,
        line=NAVY,
        size=18,
        color=WHITE,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    phases = [
        ("1", "월·화  |  Map 생성", "LiDAR · Odometry 확인\nslam_toolbox Mapping\n\n산출물\nmap.pgm · map.yaml", BLUE),
        ("2", "수  |  Localization", "저장 Map 불러오기\n/map · /odom · TF 확인\n\n산출물\nPose 확인 화면", CYAN),
        ("3", "목  |  단일 Path", "구동 Mode에 맞는 Planner\nStart → Goal Path 생성\n\n기록\nPath 길이 · Planning Time", ORANGE),
        ("4", "금  |  장애물 1개", "Obstacle Layer 갱신\n기존 Path 무효화\n\n확인\n정지 → Replanning → 재개", GREEN),
    ]
    x = 1100
    for num, title, detail, accent in phases:
        circle(doc, page, x + 2700, 4300, 800, accent, accent)
        text_box(doc, page, x + 2700, 4300, 800, 800, num, size=12, color=WHITE, bold=True, align=ParagraphAdjust.CENTER)
        box(doc, page, x, 5400, 7300, 7000, f"{title}\n\n{detail}", fill=WHITE, line=accent, size=14, color=NAVY, bold=True, align=ParagraphAdjust.CENTER)
        if num != "4":
            text_box(doc, page, x + 7200, 7800, 750, 800, "→", size=20, color=MID, bold=True, align=ParagraphAdjust.CENTER)
        x += 8100

    box(
        doc,
        page,
        1500,
        13500,
        14600,
        2300,
        "이번 주에 하지 않는 것\n복수 Candidate · VLM Selection · I2ICF 통신 구현",
        fill=PALE_RED,
        line=RED,
        size=14,
        color=RED,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    box(
        doc,
        page,
        17700,
        13500,
        14600,
        2300,
        "완료 증거\nMap 파일 · RViz 화면 · 설정값 · 성공/실패 Run Log",
        fill=PALE_GREEN,
        line=GREEN,
        size=14,
        color=GREEN,
        bold=True,
        align=ParagraphAdjust.CENTER,
    )
    source_footer(doc, page, "안전 검증 순서: Offline 확인 → 기록 데이터 Replay → Isaac Sim  |  실제 LIMO는 이번 주 범위에서 제외")
    add_notes(
        doc,
        page,
        "다음 주 목표는 SLAM Occupancy Map 저장, 저장 Map에서 Localization, 단일 Path 생성, 장애물 하나를 이용한 Replanning 확인까지다. 복수 Candidate와 VLM, I2ICF 통신은 구현하지 않고 각 단계의 설정과 성공·실패 증거를 남긴다.",
    )


def export_document(doc, output_path: pathlib.Path, filter_name: str):
    url = uno.systemPathToFileUrl(str(output_path))
    doc.storeAsURL(url, (prop("FilterName", filter_name), prop("Overwrite", True)))


def main():
    office_process, desktop = connect_office()
    doc = None
    try:
        doc = desktop.loadComponentFromURL("private:factory/simpress", "_blank", 0, ())
        pages = doc.getDrawPages()
        builders = [
            add_title_slide,
            add_agenda_slide,
            add_current_slide,
            add_slam_architecture_slide,
            add_detour_slide,
            add_i2icf_architecture_slide,
            add_roadmap_slide,
        ]
        for index, builder in enumerate(builders):
            page = new_slide(doc, pages)
            page.Name = f"slide_{index + 1}"
            builder(doc, page)

        # Remove an unused initial page if LibreOffice inserted one ahead of slide_1.
        if pages.getCount() > len(builders):
            for idx in reversed(range(pages.getCount())):
                if not pages.getByIndex(idx).Name.startswith("slide_"):
                    pages.remove(pages.getByIndex(idx))

        export_document(doc, OUTPUT_STEM.with_suffix(".pptx"), "Impress MS PowerPoint 2007 XML")
        print(f"created={OUTPUT_STEM.with_suffix('.pptx')}")
        print(f"slides={pages.getCount()}")
    finally:
        if doc is not None:
            doc.close(True)
        office_process.terminate()
        try:
            office_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            office_process.kill()


if __name__ == "__main__":
    main()
