from typing import Dict, List, Optional, Tuple

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget


LIGHT_STYLE_SHEET = """
* {
    font-family: 'Inter', 'Segoe UI', sans-serif;
    color: #1d2330;
    font-size: 13px;
}
QMainWindow {
    background-color: #f4f6fb;
}
QWidget#CentralContainer {
    background-color: transparent;
}
QFrame#topBar {
    background-color: rgba(255, 255, 255, 0.92);
    border-radius: 20px;
    border: 1px solid #e2e8fb;
}
QFrame#card, QFrame#settingsCard {
    background-color: #ffffff;
    border-radius: 18px;
    border: 1px solid #e2e7f4;
}
QWidget#profileRow {
    background-color: #ffffff;
    border-radius: 18px;
    border: 1px solid #e2e7f4;
}
QWidget#profileRow[selected="true"] {
    background-color: #eff3ff;
    border-color: #bfd0ff;
    color: #1d2330;
}
QWidget#profileRow[selected="true"] QLabel {
    color: inherit;
}
QWidget#profileRow[selected="true"] QLabel[class~="muted"] {
    color: #4b5578;
}
QWidget#profileRow:hover {
    border-color: #bfd0ff;
}
QLabel[class~="heroTitle"] {
    font-size: 18px;
    font-weight: 600;
    color: #2c388f;
}
QLabel[class~="muted"] {
    color: #7b84a7;
}
QLabel[class~="statValue"] {
    font-size: 28px;
    font-weight: 600;
    color: #2c388f;
}
QLabel[class~="cardTitle"] {
    font-size: 15px;
    font-weight: 600;
    color: #4b5578;
}
QLabel[class~="columnHeader"] {
    color: #9aa2c1;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel[class~="avatarBadge"] {
    border-radius: 16px;
    background-color: #eef3ff;
    color: #3d6dfb;
    font-weight: 600;
    font-size: 18px;
}
QLabel[class~="pillLabel"] {
    padding: 4px 10px;
    border-radius: 12px;
    background-color: #eef3ff;
    color: #39406d;
}
QLabel[class~="tagLabel"] {
    padding: 4px 10px;
    border-radius: 12px;
    background-color: #eff3ff;
    color: #39406d;
}
QPushButton {
    border-radius: 12px;
    border: 1px solid transparent;
    padding: 8px 18px;
    font-weight: 600;
    background-color: #eef2ff;
    color: #3f57f7;
}
QPushButton[class~="iconButton"] {
    font-family: 'Segoe UI Symbol', 'Segoe UI', sans-serif;
    font-size: 18px;
    color: #3f57f7;
}
QPushButton:hover {
    background-color: #e0e7ff;
}
QPushButton:pressed {
    background-color: #cfd9ff;
}
QPushButton[class~="primary"] {
    background-color: #3d6dfb;
    color: #ffffff;
    border: none;
}
QPushButton[class~="primary"]:hover {
    background-color: #335eef;
}
QPushButton[class~="danger"] {
    background-color: #fde2e1;
    color: #c62828;
    border: none;
}
QPushButton[class~="danger"]:hover {
    background-color: #fbd0cd;
}
QPushButton[class~="ghost"] {
    background-color: #ffffff;
    border: 1px solid #cdd6f5;
    color: #3f57f7;
}
QPushButton[class~="nav"] {
    background-color: transparent;
    color: #7b84a7;
    padding: 6px 16px;
    border-radius: 999px;
}
QPushButton[class~="nav"]:checked {
    background-color: #e1e7ff;
    color: #2b3dd9;
}
QPushButton[class~="tagChip"] {
    background-color: #f1f4ff;
    color: #5b6295;
    padding: 4px 14px;
    border-radius: 999px;
    border: 1px solid transparent;
}
QPushButton[class~="tagChip"]:checked {
    background-color: #3d6dfb;
    color: #ffffff;
}
QPushButton[class~="actionCategoryBtn"] {
    background-color: #ffffff;
    border: 1px solid #d7e0f5;
    border-radius: 10px;
    padding: 10px 18px;
    color: #4b5578;
    font-weight: 600;
}
QPushButton[class~="actionCategoryBtn"]:checked {
    background-color: #3d6dfb;
    color: #ffffff;
    border-color: #3d6dfb;
}
QPushButton[class~="actionOptionBtn"] {
    background-color: #f4f6ff;
    border: 1px solid #d7e0f5;
    border-radius: 10px;
    padding: 8px 16px;
    color: #3c4370;
}
QPushButton[class~="actionOptionBtn"]:checked {
    background-color: #e5ecff;
    border-color: #3d6dfb;
    color: #1b2344;
}
#CamoufoxAutoSet QPushButton {
    padding: 4px 12px;
    border: 1px solid #d8def4;
    border-radius: 6px;
    background-color: #f7f8ff;
    color: #4b5578;
}
#CamoufoxAutoSet QPushButton:checked {
    background-color: #3f57f7;
    color: #ffffff;
}
QLineEdit, QTextEdit, QComboBox, QListWidget, QSpinBox, QDoubleSpinBox {
    background-color: #fdfdff;
    border: 1px solid #d7e0f5;
    border-radius: 12px;
    padding: 8px;
    selection-background-color: #3d6dfb;
    selection-color: #ffffff;
}
QLineEdit[class~="search"] {
    padding-left: 18px;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    border-radius: 12px;
    border: 1px solid #d7e0f5;
    background-color: #ffffff;
    selection-background-color: #eff3ff;
    selection-color: #1d2330;
}
QListWidget {
    border-radius: 16px;
}
QListWidget::item {
    margin: 6px 8px;
    padding: 12px;
    border-radius: 12px;
    background-color: transparent;
}
QListWidget::item:selected {
    background-color: #e5ecff;
    color: #1b2344;
}
QListWidget#accountsList::item:selected {
    background-color: transparent;
    color: inherit;
}
QMenu {
    background-color: #fcfdff;
    color: #1d2330;
    border: 1px solid #d7e0f5;
    border-radius: 12px;
    padding: 6px;
}
QMenu::item {
    color: #1d2330;
    padding: 6px 12px;
    border-radius: 8px;
    background-color: transparent;
}
QMenu::item:selected {
    background-color: #e5ecff;
    color: #1b2344;
}
QMenu::separator {
    height: 1px;
    background-color: #e1e6f7;
    margin: 4px 8px;
}
QFrame#actionPickerDivider {
    border: none;
    background-color: #e1e6f7;
    min-height: 1px;
    max-height: 1px;
}
QTextEdit {
    min-height: 110px;
}
QTextEdit#logView {
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 12px;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 10px;
    margin: 4px;
}
QScrollBar::handle:vertical {
    background-color: rgba(61, 109, 251, 0.35);
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    border: none;
    background: transparent;
}
"""


DARK_STYLE_SHEET = """
* {
    font-family: 'Inter', 'Segoe UI', sans-serif;
    color: #f1f4ff;
    font-size: 13px;
}
QMainWindow {
    background-color: #0f111b;
}
QWidget#CentralContainer {
    background-color: transparent;
}
QFrame#topBar {
    background-color: #191f2f;
    border-radius: 20px;
    border: 1px solid #2c3450;
}
QFrame#card, QFrame#settingsCard {
    background-color: #171c2c;
    border-radius: 18px;
    border: 1px solid #2a3246;
}
QWidget#profileRow {
    background-color: #171c2c;
    border-radius: 18px;
    border: 1px solid #262f45;
}
QWidget#profileRow[selected="true"] {
    background-color: #1f2b44;
    border-color: #3a4c73;
    color: #f6f8ff;
}
QWidget#profileRow[selected="true"] QLabel {
    color: inherit;
}
QWidget#profileRow[selected="true"] QLabel[class~="muted"] {
    color: #bac4ff;
}
QWidget#profileRow:hover {
    border-color: #3a4c73;
}
QLabel[class~="heroTitle"] {
    font-size: 18px;
    font-weight: 600;
    color: #d7deff;
}
QLabel[class~="muted"] {
    color: #929ac4;
}
QLabel[class~="statValue"] {
    font-size: 28px;
    font-weight: 600;
    color: #8ab2ff;
}
QLabel[class~="cardTitle"] {
    font-size: 15px;
    font-weight: 600;
    color: #c9d4ff;
}
QLabel[class~="columnHeader"] {
    color: #8692bf;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel[class~="avatarBadge"] {
    border-radius: 16px;
    background-color: #1f2b4a;
    color: #b8c6ff;
    font-weight: 600;
    font-size: 18px;
}
QLabel[class~="pillLabel"] {
    padding: 4px 10px;
    border-radius: 12px;
    background-color: #1f2844;
    color: #c7d1ff;
}
QLabel[class~="tagLabel"] {
    padding: 4px 10px;
    border-radius: 12px;
    background-color: #223152;
    color: #c7d1ff;
}
QPushButton {
    border-radius: 12px;
    border: 1px solid transparent;
    padding: 8px 18px;
    font-weight: 600;
    background-color: #283354;
    color: #d9e0ff;
}
QPushButton[class~="iconButton"] {
    font-family: 'Segoe UI Symbol', 'Segoe UI', sans-serif;
    font-size: 18px;
    color: #bac7ff;
}
QPushButton:hover {
    background-color: #323d5f;
}
QPushButton:pressed {
    background-color: #202945;
}
QPushButton[class~="primary"] {
    background-color: #4c6cff;
    color: #ffffff;
    border: none;
}
QPushButton[class~="primary"]:hover {
    background-color: #415fef;
}
QPushButton[class~="danger"] {
    background-color: #55202f;
    color: #ffb5c1;
    border: none;
}
QPushButton[class~="danger"]:hover {
    background-color: #662538;
}
QPushButton[class~="ghost"] {
    background-color: transparent;
    border: 1px solid #3b476b;
    color: #d7deff;
}
QPushButton[class~="nav"] {
    background-color: transparent;
    color: #99a4cd;
    padding: 6px 16px;
    border-radius: 999px;
}
QPushButton[class~="nav"]:checked {
    background-color: #273255;
    color: #ffffff;
}
QPushButton[class~="tagChip"] {
    background-color: #1e2745;
    color: #c9d2ff;
    padding: 4px 14px;
    border-radius: 999px;
    border: 1px solid transparent;
}
QPushButton[class~="tagChip"]:checked {
    background-color: #4c6cff;
    color: #ffffff;
}
QPushButton[class~="actionCategoryBtn"] {
    background-color: #1b2239;
    border: 1px solid #323c59;
    border-radius: 10px;
    padding: 10px 18px;
    color: #c1cdfb;
    font-weight: 600;
}
QPushButton[class~="actionCategoryBtn"]:checked {
    background-color: #4c6cff;
    border-color: #4c6cff;
    color: #ffffff;
}
QPushButton[class~="actionOptionBtn"] {
    background-color: #1a2238;
    border: 1px solid #2f3954;
    border-radius: 10px;
    padding: 8px 16px;
    color: #cdd6ff;
}
QPushButton[class~="actionOptionBtn"]:checked {
    background-color: #2b3561;
    border-color: #4c6cff;
    color: #ffffff;
}
#CamoufoxAutoSet QPushButton {
    padding: 4px 12px;
    border: 1px solid #3a4564;
    border-radius: 6px;
    background-color: #1d243b;
    color: #c9d2f8;
}
#CamoufoxAutoSet QPushButton:checked {
    background-color: #4c6cff;
    color: #ffffff;
}
QLineEdit, QTextEdit, QComboBox, QListWidget, QSpinBox, QDoubleSpinBox {
    background-color: #111729;
    border: 1px solid #2c344f;
    border-radius: 12px;
    padding: 8px;
    selection-background-color: #4c6cff;
    selection-color: #ffffff;
}
QLineEdit[class~="search"] {
    padding-left: 18px;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    border-radius: 12px;
    border: 1px solid #2c344f;
    background-color: #0f1525;
    selection-background-color: #283355;
    selection-color: #f1f4ff;
}
QListWidget {
    border-radius: 16px;
}
QListWidget::item {
    margin: 6px 8px;
    padding: 12px;
    border-radius: 12px;
    background-color: transparent;
}
QListWidget::item:selected {
    background-color: #273255;
    color: #ffffff;
}
QListWidget#accountsList::item:selected {
    background-color: transparent;
    color: inherit;
}
QMenu {
    background-color: #0f1424;
    color: #f1f4ff;
    border: 1px solid #2a314b;
    border-radius: 12px;
    padding: 6px;
}
QMenu::item {
    color: #f1f4ff;
    padding: 6px 12px;
    border-radius: 8px;
    background-color: transparent;
}
QMenu::item:selected {
    background-color: #273255;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background-color: #242c45;
    margin: 4px 8px;
}
QFrame#actionPickerDivider {
    border: none;
    background-color: #242c45;
    min-height: 1px;
    max-height: 1px;
}
QTextEdit {
    min-height: 110px;
}
QTextEdit#logView {
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 12px;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 10px;
    margin: 4px;
}
QScrollBar::handle:vertical {
    background-color: rgba(76, 108, 255, 0.4);
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    border: none;
    background: transparent;
}
"""

CAMOUFLOW_LIGHT_STYLE_SHEET = """
* {
    font-family: 'Inter', 'Segoe UI', sans-serif;
    color: #1d2330;
    font-size: 13px;
}
QMainWindow {
    background-color: #f7f4f1;
}
QWidget#CentralContainer {
    background-color: transparent;
}
QFrame#topBar {
    background-color: rgba(255, 255, 255, 0.92);
    border-radius: 20px;
    border: 1px solid #efe2d7;
}
QFrame#card, QFrame#settingsCard {
    background-color: #ffffff;
    border-radius: 18px;
    border: 1px solid #f0e3d8;
}
QWidget#profileRow {
    background-color: #ffffff;
    border-radius: 18px;
    border: 1px solid #f0e3d8;
}
QWidget#profileRow[selected="true"] {
    background-color: #fff1e4;
    border-color: #ffc59b;
    color: #1d2330;
}
QWidget#profileRow[selected="true"] QLabel {
    color: inherit;
}
QWidget#profileRow[selected="true"] QLabel[class~="muted"] {
    color: #4b5578;
}
QWidget#profileRow:hover {
    border-color: #ffc59b;
}
QLabel[class~="heroTitle"] {
    font-size: 18px;
    font-weight: 600;
    color: #8a3a00;
}
QLabel[class~="muted"] {
    color: #7b84a7;
}
QLabel[class~="statValue"] {
    font-size: 28px;
    font-weight: 600;
    color: #8a3a00;
}
QLabel[class~="cardTitle"] {
    font-size: 15px;
    font-weight: 600;
    color: #4b5578;
}
QLabel[class~="columnHeader"] {
    color: #9aa2c1;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel[class~="avatarBadge"] {
    border-radius: 16px;
    background-color: #fff1e4;
    color: #ff7a18;
    font-weight: 600;
    font-size: 18px;
}
QLabel[class~="pillLabel"] {
    padding: 4px 10px;
    border-radius: 12px;
    background-color: #fff1e4;
    color: #4a3f37;
}
QLabel[class~="tagLabel"] {
    padding: 4px 10px;
    border-radius: 12px;
    background-color: #fff1e4;
    color: #4a3f37;
}
QPushButton {
    border-radius: 12px;
    border: 1px solid transparent;
    padding: 8px 18px;
    font-weight: 600;
    background-color: #fff1e4;
    color: #b34700;
}
QPushButton[class~="iconButton"] {
    font-family: 'Segoe UI Symbol', 'Segoe UI', sans-serif;
    font-size: 18px;
    color: #b34700;
}
QPushButton:hover {
    background-color: #ffe6d1;
}
QPushButton:pressed {
    background-color: #ffd4b2;
}
QPushButton[class~="primary"] {
    background-color: #ff7a18;
    color: #ffffff;
    border: none;
}
QPushButton[class~="primary"]:hover {
    background-color: #f56b00;
}
QPushButton[class~="danger"] {
    background-color: #fde2e1;
    color: #c62828;
    border: none;
}
QPushButton[class~="danger"]:hover {
    background-color: #fbd0cd;
}
QPushButton[class~="ghost"] {
    background-color: #ffffff;
    border: 1px solid #efcfb7;
    color: #b34700;
}
QPushButton[class~="nav"] {
    background-color: transparent;
    color: #7b84a7;
    padding: 6px 16px;
    border-radius: 999px;
}
QPushButton[class~="nav"]:checked {
    background-color: #fff1e4;
    color: #8a3a00;
}
QPushButton[class~="tagChip"] {
    background-color: #fff7f0;
    color: #5b6295;
    padding: 4px 14px;
    border-radius: 999px;
    border: 1px solid transparent;
}
QPushButton[class~="tagChip"]:checked {
    background-color: #ff7a18;
    color: #ffffff;
}
QPushButton[class~="actionCategoryBtn"] {
    background-color: #ffffff;
    border: 1px solid #f0e3d8;
    border-radius: 10px;
    padding: 10px 18px;
    color: #4b5578;
    font-weight: 600;
}
QPushButton[class~="actionCategoryBtn"]:checked {
    background-color: #ff7a18;
    color: #ffffff;
    border-color: #ff7a18;
}
QPushButton[class~="actionOptionBtn"] {
    background-color: #fff7f0;
    border: 1px solid #f0e3d8;
    border-radius: 10px;
    padding: 8px 16px;
    color: #3c4370;
}
QPushButton[class~="actionOptionBtn"]:checked {
    background-color: #ffe6d1;
    border-color: #ff7a18;
    color: #1b2344;
}
#CamoufoxAutoSet QPushButton {
    padding: 4px 12px;
    border: 1px solid #f0e3d8;
    border-radius: 6px;
    background-color: #fff7f0;
    color: #4b5578;
}
#CamoufoxAutoSet QPushButton:checked {
    background-color: #ff7a18;
    color: #ffffff;
}
QLineEdit, QTextEdit, QComboBox, QListWidget, QSpinBox, QDoubleSpinBox {
    background-color: #fffefd;
    border: 1px solid #f0e3d8;
    border-radius: 12px;
    padding: 8px;
    selection-background-color: #ff7a18;
    selection-color: #ffffff;
}
QLineEdit[class~="search"] {
    padding-left: 18px;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    border-radius: 12px;
    border: 1px solid #f0e3d8;
    background-color: #ffffff;
    selection-background-color: #fff1e4;
    selection-color: #1d2330;
}
QListWidget {
    border-radius: 16px;
}
QListWidget::item {
    margin: 6px 8px;
    padding: 12px;
    border-radius: 12px;
    background-color: transparent;
}
QListWidget::item:selected {
    background-color: #fff1e4;
    color: #1b2344;
}
QListWidget#accountsList::item:selected {
    background-color: transparent;
    color: inherit;
}
QMenu {
    background-color: #fffefd;
    color: #1d2330;
    border: 1px solid #f0e3d8;
    border-radius: 12px;
    padding: 6px;
}
QMenu::item {
    color: #1d2330;
    padding: 6px 12px;
    border-radius: 8px;
    background-color: transparent;
}
QMenu::item:selected {
    background-color: #fff1e4;
    color: #1b2344;
}
QMenu::separator {
    height: 1px;
    background-color: #f0e3d8;
    margin: 4px 8px;
}
QFrame#actionPickerDivider {
    border: none;
    background-color: #f0e3d8;
    min-height: 1px;
    max-height: 1px;
}
QTextEdit {
    min-height: 110px;
}
QTextEdit#logView {
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 12px;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 10px;
    margin: 4px;
}
QScrollBar::handle:vertical {
    background-color: rgba(255, 122, 24, 0.35);
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    border: none;
    background: transparent;
}
"""

CAMOUFLOW_DARK_STYLE_SHEET = """
* {
    font-family: 'Inter', 'Segoe UI', sans-serif;
    color: #f6f1ec;
    font-size: 13px;
}
QMainWindow {
    background-color: #111015;
}
QWidget#CentralContainer {
    background-color: transparent;
}
QFrame#topBar {
    background-color: #1b1a21;
    border-radius: 20px;
    border: 1px solid #2c2a33;
}
QFrame#card, QFrame#settingsCard {
    background-color: #17161c;
    border-radius: 18px;
    border: 1px solid #2a2831;
}
QWidget#profileRow {
    background-color: #17161c;
    border-radius: 18px;
    border: 1px solid #26242c;
}
QWidget#profileRow[selected="true"] {
    background-color: #2a221f;
    border-color: #4a3a33;
    color: #fff7f0;
}
QWidget#profileRow[selected="true"] QLabel {
    color: inherit;
}
QWidget#profileRow[selected="true"] QLabel[class~="muted"] {
    color: #ffd7b5;
}
QWidget#profileRow:hover {
    border-color: #4a3a33;
}
QLabel[class~="heroTitle"] {
    font-size: 18px;
    font-weight: 600;
    color: #ffd7b5;
}
QLabel[class~="muted"] {
    color: #b8afab;
}
QLabel[class~="statValue"] {
    font-size: 28px;
    font-weight: 600;
    color: #ffb37a;
}
QLabel[class~="cardTitle"] {
    font-size: 15px;
    font-weight: 600;
    color: #e6dbd6;
}
QLabel[class~="columnHeader"] {
    color: #a79f9b;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel[class~="avatarBadge"] {
    border-radius: 16px;
    background-color: #2a221f;
    color: #ffb37a;
    font-weight: 600;
    font-size: 18px;
}
QLabel[class~="pillLabel"] {
    padding: 4px 10px;
    border-radius: 12px;
    background-color: #242026;
    color: #f0e3d8;
}
QLabel[class~="tagLabel"] {
    padding: 4px 10px;
    border-radius: 12px;
    background-color: #242026;
    color: #f0e3d8;
}
QPushButton {
    border-radius: 12px;
    border: 1px solid transparent;
    padding: 8px 18px;
    font-weight: 600;
    background-color: #2a2831;
    color: #ffd7b5;
}
QPushButton[class~="iconButton"] {
    font-family: 'Segoe UI Symbol', 'Segoe UI', sans-serif;
    font-size: 18px;
    color: #ffd7b5;
}
QPushButton:hover {
    background-color: #35323e;
}
QPushButton:pressed {
    background-color: #23212a;
}
QPushButton[class~="primary"] {
    background-color: #ff7a18;
    color: #ffffff;
    border: none;
}
QPushButton[class~="primary"]:hover {
    background-color: #f56b00;
}
QPushButton[class~="danger"] {
    background-color: #55202f;
    color: #ffb5c1;
    border: none;
}
QPushButton[class~="danger"]:hover {
    background-color: #662538;
}
QPushButton[class~="ghost"] {
    background-color: transparent;
    border: 1px solid #3a3437;
    color: #ffd7b5;
}
QPushButton[class~="nav"] {
    background-color: transparent;
    color: #b8afab;
    padding: 6px 16px;
    border-radius: 999px;
}
QPushButton[class~="nav"]:checked {
    background-color: #2a221f;
    color: #ffffff;
}
QPushButton[class~="tagChip"] {
    background-color: #242026;
    color: #e6dbd6;
    padding: 4px 14px;
    border-radius: 999px;
    border: 1px solid transparent;
}
QPushButton[class~="tagChip"]:checked {
    background-color: #ff7a18;
    color: #ffffff;
}
QPushButton[class~="actionCategoryBtn"] {
    background-color: #1c1a22;
    border: 1px solid #2f2c36;
    border-radius: 10px;
    padding: 10px 18px;
    color: #e6dbd6;
    font-weight: 600;
}
QPushButton[class~="actionCategoryBtn"]:checked {
    background-color: #ff7a18;
    border-color: #ff7a18;
    color: #ffffff;
}
QPushButton[class~="actionOptionBtn"] {
    background-color: #1c1a22;
    border: 1px solid #2f2c36;
    border-radius: 10px;
    padding: 8px 16px;
    color: #f0e3d8;
}
QPushButton[class~="actionOptionBtn"]:checked {
    background-color: #2a221f;
    border-color: #ff7a18;
    color: #ffffff;
}
#CamoufoxAutoSet QPushButton {
    padding: 4px 12px;
    border: 1px solid #2f2c36;
    border-radius: 6px;
    background-color: #1c1a22;
    color: #e6dbd6;
}
#CamoufoxAutoSet QPushButton:checked {
    background-color: #ff7a18;
    color: #ffffff;
}
QLineEdit, QTextEdit, QComboBox, QListWidget, QSpinBox, QDoubleSpinBox {
    background-color: #121117;
    border: 1px solid #2a2831;
    border-radius: 12px;
    padding: 8px;
    selection-background-color: #ff7a18;
    selection-color: #ffffff;
}
QLineEdit[class~="search"] {
    padding-left: 18px;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    border-radius: 12px;
    border: 1px solid #2a2831;
    background-color: #121117;
    selection-background-color: #2a221f;
    selection-color: #fff7f0;
}
QListWidget {
    border-radius: 16px;
}
QListWidget::item {
    margin: 6px 8px;
    padding: 12px;
    border-radius: 12px;
    background-color: transparent;
}
QListWidget::item:selected {
    background-color: #2a221f;
    color: #ffffff;
}
QListWidget#accountsList::item:selected {
    background-color: transparent;
    color: inherit;
}
QMenu {
    background-color: #121117;
    color: #fff7f0;
    border: 1px solid #2a2831;
    border-radius: 12px;
    padding: 6px;
}
QMenu::item {
    color: #fff7f0;
    padding: 6px 12px;
    border-radius: 8px;
    background-color: transparent;
}
QMenu::item:selected {
    background-color: #2a221f;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background-color: #2a2831;
    margin: 4px 8px;
}
QFrame#actionPickerDivider {
    border: none;
    background-color: #2a2831;
    min-height: 1px;
    max-height: 1px;
}
QTextEdit {
    min-height: 110px;
}
QTextEdit#logView {
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 12px;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 10px;
    margin: 4px;
}
QScrollBar::handle:vertical {
    background-color: rgba(255, 122, 24, 0.4);
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    border: none;
    background: transparent;
}
"""


DEFAULT_THEME = "camouflow_light"

_THEMES: Dict[str, Dict[str, object]] = {
    "light": {
        "label": "Classic Light",
        "stylesheet": LIGHT_STYLE_SHEET,
        "palette": {
            QPalette.ColorRole.Window: "#f4f6fb",
            QPalette.ColorRole.Base: "#ffffff",
            QPalette.ColorRole.AlternateBase: "#f4f6fb",
            QPalette.ColorRole.Text: "#1d2330",
            QPalette.ColorRole.Button: "#eef2ff",
            QPalette.ColorRole.ButtonText: "#2b3dd9",
            QPalette.ColorRole.Highlight: "#3d6dfb",
            QPalette.ColorRole.HighlightedText: "#ffffff",
        },
    },
    "dark": {
        "label": "Classic Dark",
        "stylesheet": DARK_STYLE_SHEET,
        "palette": {
            QPalette.ColorRole.Window: "#0f111b",
            QPalette.ColorRole.Base: "#12172a",
            QPalette.ColorRole.AlternateBase: "#191f2f",
            QPalette.ColorRole.Text: "#f1f4ff",
            QPalette.ColorRole.Button: "#2b3553",
            QPalette.ColorRole.ButtonText: "#e0e4ff",
            QPalette.ColorRole.Highlight: "#4c6cff",
            QPalette.ColorRole.HighlightedText: "#ffffff",
        },
    },
    "camouflow_light": {
        "label": "CamouFlow Orange (Light)",
        "stylesheet": CAMOUFLOW_LIGHT_STYLE_SHEET,
        "palette": {
            QPalette.ColorRole.Window: "#f7f4f1",
            QPalette.ColorRole.Base: "#ffffff",
            QPalette.ColorRole.AlternateBase: "#f7f4f1",
            QPalette.ColorRole.Text: "#1d2330",
            QPalette.ColorRole.Button: "#fff1e4",
            QPalette.ColorRole.ButtonText: "#8a3a00",
            QPalette.ColorRole.Highlight: "#ff7a18",
            QPalette.ColorRole.HighlightedText: "#ffffff",
        },
    },
    "camouflow_dark": {
        "label": "CamouFlow Orange (Dark)",
        "stylesheet": CAMOUFLOW_DARK_STYLE_SHEET,
        "palette": {
            QPalette.ColorRole.Window: "#111015",
            QPalette.ColorRole.Base: "#121117",
            QPalette.ColorRole.AlternateBase: "#1b1a21",
            QPalette.ColorRole.Text: "#fff7f0",
            QPalette.ColorRole.Button: "#2a2831",
            QPalette.ColorRole.ButtonText: "#ffd7b5",
            QPalette.ColorRole.Highlight: "#ff7a18",
            QPalette.ColorRole.HighlightedText: "#ffffff",
        },
    },
}


def available_themes() -> List[Tuple[str, str]]:
    primary = ["camouflow_light", "camouflow_dark"]
    extras = [key for key in _THEMES.keys() if key not in primary]
    ordered = primary + extras
    return [(key, _THEMES[key]["label"]) for key in ordered if key in _THEMES]


def normalize_theme(theme: Optional[str]) -> str:
    key = str(theme or "").strip().lower()
    return key if key in _THEMES else DEFAULT_THEME


def apply_modern_theme(app: QApplication, theme: str = DEFAULT_THEME) -> str:
    """Apply the requested theme and return the normalized key."""
    key = normalize_theme(theme)
    theme_data = _THEMES[key]
    palette = QPalette()
    palette_data: Dict[QPalette.ColorRole, str] = theme_data["palette"]  # type: ignore[assignment]
    for role, color in palette_data.items():
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(theme_data["stylesheet"])
    return key


def create_card(parent: Optional[QWidget] = None, title: Optional[str] = None) -> Tuple[QFrame, QVBoxLayout, Optional[QLabel]]:
    """Create a rounded card frame with consistent paddings and optional title."""
    frame = QFrame(parent)
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    heading = None
    if title:
        heading = QLabel(title)
        heading.setProperty("class", "cardTitle")
        layout.addWidget(heading)
    return frame, layout, heading


__all__ = ["apply_modern_theme", "create_card", "available_themes", "normalize_theme", "DEFAULT_THEME"]
